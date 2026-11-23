import math
import hashlib

class DiskBlock:
    def __init__(self, index, size=4096):
        self.index = index
        self.status = "LIVRE"
        self.owner = None
        self.used_bytes = 0
        self.data = bytearray(size)
        self.pointers = []       # Tabela de ponteiros do i-node
        self.saved_hash = None   # Hash oficial registrado para o Antivírus
        self.track = (index * 19 + 11) % 200

    def write(self, raw_bytes):
        n = min(len(raw_bytes), len(self.data))
        self.data[:n] = raw_bytes[:n]
        self.used_bytes = n
        self.saved_hash = self.calc_hash()

    def read(self):
        return bytes(self.data[:self.used_bytes])

    def calc_hash(self):
        return hashlib.sha256(self.read()).hexdigest()


class FileNode:
    def __init__(self, name, is_dir=False, parent=None, owner="root", group="admin", perms="755"):
        self.name = name
        self.is_dir = is_dir
        self.parent = parent
        self.children = {}
        self.size = 0
        self.inode_block = None
        self.owner = owner
        self.group = group
        self.perms = perms
        self.encrypted = False


class ReservedMemory:
    """Região Estática/Fixa da RAM (4 MB) com alocação contígua (First-Fit) e compactação."""
    def __init__(self, total_kb=4096):
        self.total_kb = total_kb
        # Lista de blocos alocados: [start_kb, size_kb, name]
        self.segments = [[0, 1024, "Núcleo Base do SO"]]

    def allocate(self, name, size_kb):
        # Ordena segmentos por endereço inicial
        self.segments.sort(key=lambda s: s[0])
        cursor = 0
        for start, size, _ in self.segments:
            if start - cursor >= size_kb:
                self.segments.append([cursor, size_kb, name])
                self.segments.sort(key=lambda s: s[0])
                return cursor, cursor + size_kb
            cursor = start + size
        if self.total_kb - cursor >= size_kb:
            self.segments.append([cursor, size_kb, name])
            self.segments.sort(key=lambda s: s[0])
            return cursor, cursor + size_kb
        return None

    def free(self, name):
        for i, (start, size, proc_name) in enumerate(self.segments):
            if proc_name == name:
                self.segments.pop(i)
                return start, start + size, size
        return None

    def get_free_holes(self):
        self.segments.sort(key=lambda s: s[0])
        holes = []
        cursor = 0
        for start, size, _ in self.segments:
            if start > cursor:
                holes.append((cursor, start, start - cursor))
            cursor = start + size
        if cursor < self.total_kb:
            holes.append((cursor, self.total_kb, self.total_kb - cursor))
        return holes

    def status(self):
        print("> memory_status --reserved")
        print(f"--- MAPA DA ÁREA CRÍTICA/RESERVADA DA RAM (Total: {self.total_kb // 1024} MB - Alocação Fixa) ---")
        self.segments.sort(key=lambda s: s[0])
        cursor, hole_idx = 0, 1
        for start, size, name in self.segments:
            if start > cursor:
                h_size = start - cursor
                print(f"[{cursor/1024:.1f} MB - {start/1024:.1f} MB] : FRAGMENTO LIVRE {hole_idx:<3} ({h_size} KB)  [LIVRE - LACUNA]")
                hole_idx += 1
            print(f"[{start/1024:.1f} MB - {(start+size)/1024:.1f} MB] : {name:<19} ({size} KB)  [OCUPADO]")
            cursor = start + size
        if cursor < self.total_kb:
            h_size = self.total_kb - cursor
            print(f"[{cursor/1024:.1f} MB - {self.total_kb/1024:.1f} MB] : FRAGMENTO LIVRE {hole_idx:<3} ({h_size} KB)  [LIVRE - LACUNA]")

        holes = self.get_free_holes()
        total_free = sum(h[2] for h in holes)
        max_contig = max((h[2] for h in holes), default=0)
        has_ext_frag = len(holes) > 1

        print("\n--- DIAGNÓSTICO DE FRAGMENTAÇÃO EXTERNA ---")
        print(f"Total de Memória Livre na Área Reservada : {total_free} KB ({total_free/1024:.1f} MB)")
        print(f"Maior Bloco Contíguo Disponível          : {max_contig} KB ({max_contig/1024:.1f} MB)")
        print(f"Fragmentação Externa Detectada           : {'SIM (' + str(len(holes)) + ' fragmentos não contíguos)' if has_ext_frag else 'NÃO'}")
        if has_ext_frag and total_free > max_contig:
            req_test = max_contig + 512
            if req_test <= total_free:
                print(f"Status: Uma requisição contígua de {req_test} KB falhará por ausência de bloco único.\n")

    def compact(self):
        print("> memory_compact --reserved")
        print("[EXECUTANDO COMPACTAÇÃO DA ÁREA RESERVADA DA RAM]")
        print("Realocando blocos contíguos para eliminar a fragmentação externa...")
        self.segments.sort(key=lambda s: s[0])
        cursor = 0
        moved = False
        for seg in self.segments:
            old_start, size, name = seg
            if old_start != cursor:
                print(f"- Mapeamento de '{name}': [{old_start/1024:.1f} MB a {(old_start+size)/1024:.1f} MB] -> Ajustado para: [{cursor/1024:.1f} MB a {(cursor+size)/1024:.1f} MB]")
                seg[0] = cursor
                moved = True
            cursor += size
        if not moved:
            print("- Memória já está contígua.")

        print("\n--- MAPA APÓS COMPACTAÇÃO ---")
        for start, size, name in self.segments:
            print(f"[{start/1024:.1f} MB - {(start+size)/1024:.1f} MB] : {name:<19} ({size} KB)  [OCUPADO]")
        free_end = self.total_kb - cursor
        if free_end > 0:
            print(f"[{cursor/1024:.1f} MB - {self.total_kb/1024:.1f} MB] : Bloco Livre Contíguo ({free_end} KB) [LIVRE]")
        print(f"Resultado: Fragmentação externa eliminada. Maior bloco contíguo: {free_end} KB.\n")


class VirtualMemoryManager:
    """Região Dinâmica Paginada com Tabela de Páginas, Swapping real e algoritmo LRU."""
    def __init__(self, total_frames=128, page_size=4096):
        self.total_frames = total_frames
        self.page_size = page_size
        # Molduras físicas da RAM: frame_id -> {"pid": int, "proc": str, "page": int, "last_used": int, "data": bytearray}
        self.frames = {}
        self.swap_space = {}  # Memória secundária (Swap): (proc_name, page_num) -> bytearray
        self.page_tables = {} # proc_name -> {"pid": int, "size_bytes": int, "pages": {page_num: frame_id ou None}}
        self.clock = 100
        self.next_pid = 101

    def create_process(self, name, size_kb):
        size_bytes = size_kb * 1024
        num_pages = math.ceil(size_bytes / self.page_size)
        pid = self.next_pid
        self.next_pid += 1

        self.page_tables[name] = {
            "pid": pid,
            "size_bytes": size_bytes,
            "pages": {p: None for p in range(num_pages)}
        }

        print(f"> create_process --name \"{name}\" --size {size_kb}KB --type normal")
        print("[CRIAÇÃO DE PROCESSO NÃO CRÍTICO - MEMÓRIA VIRTUAL]")
        print(f"Tamanho do Processo : {size_kb} KB ({size_bytes} Bytes)")
        print(f"Tamanho da Página   : {self.page_size // 1024} KB ({self.page_size} Bytes)")
        print(f"Cálculo de Páginas  : {size_bytes / self.page_size:.1f} -> Requer {num_pages} Páginas Lógicas (Páginas {', '.join(map(str, range(num_pages)))}).\n")

        print("--- ANÁLISE DE FRAGMENTAÇÃO INTERNA ---")
        rem = size_bytes
        total_frag = 0
        for p in range(num_pages):
            used = min(rem, self.page_size)
            perc = (used / self.page_size) * 100
            extra = f" ({perc:.0f}% de uso)" if used < self.page_size else f" ({perc:.0f}%)"
            print(f"Página Lógica {p} : {used} Bytes ocupados{extra}")
            if used < self.page_size:
                total_frag += (self.page_size - used)
            rem -= used

        print(f"Fragmentação Interna Total: {total_frag} Bytes de desperdício na Página Lógica {num_pages - 1}.")
        print("Status: Tabela de Páginas gerada sem alocar molduras na RAM (Alocação por demanda).\n")

    def map_page_direct(self, proc_name, page_num, frame_id, age_ms=10):
        """Carrega uma página específica em uma moldura física (para estado inicial de execução)."""
        pt = self.page_tables[proc_name]
        pt["pages"][page_num] = frame_id
        self.frames[frame_id] = {
            "pid": pt["pid"],
            "proc": proc_name,
            "page": page_num,
            "last_used": self.clock - age_ms,
            "data": bytearray(f"DATA_{proc_name}_P{page_num}".encode())
        }

    def fill_remaining_frames_for_pressure(self, holder_proc="Bg_Service", holder_pid=102):
        """Preenche as molduras livres restantes para demonstrar pressão de memória e disparo do LRU."""
        p_idx = 0
        for f_id in range(self.total_frames):
            if f_id not in self.frames:
                # Moldura 88 recebe a página mais antiga (45ms sem uso) para ser escolhida pelo LRU real
                age = 45 if f_id == 88 else 15
                self.frames[f_id] = {
                    "pid": holder_pid,
                    "proc": holder_proc,
                    "page": p_idx,
                    "last_used": self.clock - age,
                    "data": bytearray(f"SWAP_PAYLOAD_PID{holder_pid}_P{p_idx}".encode())
                }
                p_idx += 1

    def translate_address(self, proc_name, page_num):
        print(f"> translate_address --process {proc_name} --page {page_num}")
        print("[TRADUÇÃO DE ENDEREÇO: PÁGINA LÓGICA -> MOLDURA FÍSICA]")
        pt = self.page_tables.get(proc_name)
        frame_id = pt["pages"].get(page_num) if pt else None
        if frame_id is not None:
            self.clock += 1
            self.frames[frame_id]["last_used"] = self.clock
            print(f"Solicitação: Página Lógica {page_num} -> Mapeada na Moldura Física {frame_id} (RAM Dinâmica) [HIT]\n")
        else:
            print(f"Solicitação: Página Lógica {page_num} -> Não mapeada na RAM [PAGE FAULT]\n")

    def access_page(self, proc_name, page_num, instruction):
        print(f'> execute_step --process {proc_name} --instruction "{instruction}"')
        print("[CPU - REFERÊNCIA DE MEMÓRIA EM EXECUÇÃO]")
        print(f"{proc_name} requisita acesso à Página Lógica {page_num}...")
        pt = self.page_tables[proc_name]
        frame_id = pt["pages"][page_num]

        if frame_id is not None:
            self.clock += 1
            self.frames[frame_id]["last_used"] = self.clock
            print(f"- Consulta Tabela de Páginas -> HIT na Moldura Física {frame_id}.\n")
            return

        print(f"- Consulta Tabela de Páginas -> Página Lógica {page_num} NÃO ESTÁ NA RAM!\n")
        print(f"[PAGE FAULT DETECTADO]: Página Lógica {page_num} ausente na RAM!")

        # Verifica se há moldura livre; se cheia, executa LRU real
        free_frames = [f for f in range(self.total_frames) if f not in self.frames]
        if free_frames:
            chosen_frame = free_frames[0]
        else:
            print("Memória RAM cheia. Executando Substituição de Página (Algoritmo LRU):")
            # Seleção real da moldura com menor timestamp 'last_used'
            victim_frame = min(self.frames.keys(), key=lambda f: self.frames[f]["last_used"])
            victim = self.frames[victim_frame]
            idle_ms = self.clock - victim["last_used"]

            print(f"- Analisando histórico de acesso: Página Lógica {victim['page']} do PID {victim['pid']} não é usada há {idle_ms}ms (Mais antiga).")
            # Salva os bytes reais da vítima na área de Swap (Disco)
            self.swap_space[(victim["proc"], victim["page"])] = victim["data"]
            if victim["proc"] in self.page_tables:
                self.page_tables[victim["proc"]]["pages"][victim["page"]] = None
            print(f"- Removendo Página Lógica {victim['page']} do PID {victim['pid']} da RAM -> Salvando no Swap (Disco).")
            chosen_frame = victim_frame

        # Carrega a página solicitada (do Swap se existir, ou nova) na moldura escolhida
        restored_data = self.swap_space.pop((proc_name, page_num), bytearray(f"DATA_{proc_name}_P{page_num}".encode()))
        self.clock += 1
        self.frames[chosen_frame] = {
            "pid": pt["pid"],
            "proc": proc_name,
            "page": page_num,
            "last_used": self.clock,
            "data": restored_data
        }
        pt["pages"][page_num] = chosen_frame
        print(f"- Carregando Página Lógica {page_num} do {proc_name} na Moldura Física {chosen_frame} (RAM Dinâmica).")
        print(f"- Tabela de Páginas atualizada: Página Lógica {page_num} ---> Moldura Física {chosen_frame}.\n")

    def memory_summary(self):
        used_frames = len(self.frames)
        print("--- RESUMO DE OCUPAÇÃO DE MEMÓRIA ---")
        print(f"RAM Dinâmica (Paginada): {used_frames}/{self.total_frames} molduras ocupadas ({used_frames * 4} KB / {self.total_frames * 4} KB) | Páginas em Swap: {len(self.swap_space)}\n")


class FileSystem:
    def __init__(self, block_size=4096, total_blocks=16):
        self.block_size = block_size
        self.total_blocks = total_blocks
        self.disk = [DiskBlock(i, block_size) for i in range(total_blocks)]
        
        # 3 Discos físicos reais para o RAID 5
        self.raid_disks = [bytearray(block_size) for _ in range(3)]
        self.io_queue = []
        self.head_pos = 53

        # Etapa 4: Subsistema de Memória Híbrida (Reservada Contígua + Virtual Paginada)
        self.reserved_mem = ReservedMemory(total_kb=4096)
        self.virtual_mem = VirtualMemoryManager(total_frames=128, page_size=block_size)

        # Inicializa Raiz '/' no Bloco 0
        self.root = FileNode("/", is_dir=True)
        self.root.parent = self.root
        self.cwd = self.root
        self.disk[0].status = "INODE_RAIZ"
        self.disk[0].owner = "Diretório '/'"
        self.disk[0].write(b"ROOT_DIR")

        # Usuários e Autenticação (Etapa 3)
        self.users = {
            "root": {"hash": self._hash_pw("admin123"), "group": "admin"},
            "carlos": {"hash": self._hash_pw("senha123"), "group": "devs"}
        }
        self.user = "root"
        self.group = "admin"
        self.mode = "MODO_KERNEL"

    # --- NAVEGAÇÃO (Caminhos Absolutos e Relativos) ---
    def _resolve(self, path):
        if path == "/":
            return self.root, "", self.root
        curr = self.root if path.startswith("/") else self.cwd
        parts = [p for p in path.split("/") if p]
        for p in parts[:-1]:
            if p == "..":
                curr = curr.parent
            elif p != "." and p in curr.children and curr.children[p].is_dir:
                curr = curr.children[p]
            else:
                return None, None, None
        last = parts[-1] if parts else ""
        if last == "..":
            return curr.parent.parent, curr.parent.name, curr.parent
        return curr, last, curr.children.get(last)

    def _abs_path(self, node):
        if node == self.root:
            return "/"
        parts = []
        while node != self.root:
            parts.append(node.name)
            node = node.parent
        return "/" + "/".join(reversed(parts))

    # --- ETAPA 3: SEGURANÇA, ACL, CRIPTOGRAFIA E ANTIVÍRUS ---
    def _hash_pw(self, pw):
        return hashlib.sha256((pw + "SALT_SO").encode()).hexdigest()

    def login(self, username, password):
        print(f"> login --user {username}\nSenha: {'*' * len(password)}")
        if username in self.users and self.users[username]["hash"] == self._hash_pw(password):
            self.user = username
            self.group = self.users[username]["group"]
            self.mode = "MODO_KERNEL" if username == "root" else "MODO_USUARIO"
            print(f"Autenticado com sucesso. Usuário: '{self.user}' | Grupo: '{self.group}' | Modo: {self.mode}\n")

    def _check_acl(self, node, path, req_perm, verbose=False):
        if self.mode == "MODO_KERNEL":
            return True
        idx = 0 if self.user == node.owner else (1 if self.group == node.group else 2)
        val = int(node.perms[idx])
        allowed = (req_perm == 'r' and val >= 4) or (req_perm == 'w' and (val & 2)) or (req_perm == 'x' and (val & 1))

        if verbose or not allowed:
            rwx = "".join({'7':'rwx','6':'rw-','5':'r-x','4':'r--','3':'-wx','2':'-w-','1':'--x','0':'---'}[c] for c in node.perms)
            act = {'r': 'LEITURA', 'w': 'ESCRITA', 'x': 'EXECUÇÃO'}[req_perm]
            print(f"[SISTEMA DE SEGURANÇA - VERIFICAÇÃO DE ACL]\nObjeto      : {path}")
            print(f"Proprietário: {node.owner} (Grupo: {node.group})\nPermissões  : {rwx} ({node.perms})")
            print(f"Ação Pedida : {act} por '{self.user}' (Grupo: {self.group})\n")
            if not allowed:
                print(f"[NEGADO]: O usuário '{self.user}' não possui permissão de {act.lower()} no objeto '{path}'.")
                print("Tentativa não autorizada registrada nos logs do sistema.\n")
        return allowed

    def set_acl(self, path, owner, group, perms):
        _, _, node = self._resolve(path)
        if node and self.mode == "MODO_KERNEL":
            node.owner, node.group, node.perms = owner, group, perms

    def encrypt_file(self, path, key):
        print(f'> encrypt_file {path} --key "{key}"')
        _, _, node = self._resolve(path)
        if not node or not self._check_acl(node, path, 'w'):
            return
        key_bytes = hashlib.sha256(key.encode()).digest()
        for b_idx in self.disk[node.inode_block].pointers:
            raw = self.disk[b_idx].read()
            cipher = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(raw))
            self.disk[b_idx].write(cipher)
        node.encrypted = True
        sample = "0x" + self.disk[self.disk[node.inode_block].pointers[0]].read()[:4].hex().upper()
        print(f"Arquivo '{path}' criptografado com sucesso.")
        print(f'Conteúdo gravado nos blocos físicos: "{sample}... (Encrypted Ciphertext)"\n')

    def antivirus_scan(self):
        print("> antivirus_scan /\n[MÓDULO DE SEGURANÇA - VARREDURA DE INTEGRIDADE]")
        files = []
        def get_files(n):
            for c in n.children.values():
                get_files(c) if c.is_dir else files.append(c)
        get_files(self.root)
        print(f"Analisando {len(files)} arquivos em busca de assinaturas maliciosas e hashes corrompidos...")

        for f in files:
            p = self._abs_path(f)
            corrupted = any(self.disk[b].calc_hash() != self.disk[b].saved_hash for b in self.disk[f.inode_block].pointers)
            if corrupted:
                print(f"\n- {p:<26}: [ALERTA] Hash do bloco difere do registro oficial!")
                print("  Resultado: Possível modificação direta não autorizada no bloco do disco.")
            else:
                tag = "[OK - Criptografado e Íntegro]" if f.encrypted else "[OK - Íntegro]"
                print(f"- {p:<26}: {tag}")
        print()

    # --- ETAPA 1: CRUD E ALOCAÇÃO INDEXADA (i-node) ---
    def mkdir(self, path, silent=False):
        if not silent:
            print(f"> mkdir {path}")
        parent, name, exist = self._resolve(path)
        if parent and not exist and self._check_acl(parent, self._abs_path(parent), 'w'):
            parent.children[name] = FileNode(name, is_dir=True, parent=parent, owner=self.user, group=self.group)

    def create(self, path, size_kb, silent=False):
        if not silent:
            print(f"> create {path} --size {size_kb}")
        parent, name, exist = self._resolve(path)
        if not parent or exist or not self._check_acl(parent, self._abs_path(parent), 'w'):
            return

        size_bytes = int(size_kb.upper().replace("KB", "")) * 1024
        blocks_needed = math.ceil(size_bytes / self.block_size)
        free = [b.index for b in self.disk if b.status == "LIVRE"]
        if len(free) < blocks_needed + 1:
            return print("Erro: Disco cheio.")

        fnode = FileNode(name, is_dir=False, parent=parent, owner=self.user, group=self.group)
        fnode.size = size_bytes
        abs_p = (self._abs_path(parent) + "/" + name).replace("//", "/")

        inode_idx = free.pop(0)
        data_idxs = free[:blocks_needed]
        self.disk[inode_idx].status = f"INODE_{name.split('.')[0].upper()}"
        self.disk[inode_idx].owner = f"Arquivo '{abs_p}'"
        self.disk[inode_idx].pointers = data_idxs
        self.disk[inode_idx].write(str(data_idxs).encode())
        fnode.inode_block = inode_idx

        payload = (f"DADOS_DO_ARQUIVO_{name}_".encode() * 512)[:size_bytes]
        rem = size_bytes
        for i, b_idx in enumerate(data_idxs):
            chunk = payload[i * self.block_size : i * self.block_size + min(rem, self.block_size)]
            self.disk[b_idx].status = "DADO"
            self.disk[b_idx].owner = abs_p
            self.disk[b_idx].write(chunk)
            self.io_queue.append(self.disk[b_idx].track)
            rem -= len(chunk)

        parent.children[name] = fnode

    def read_file(self, path):
        print(f"> read_file {path}")
        _, _, node = self._resolve(path)
        if node and not node.is_dir and self._check_acl(node, path, 'r', verbose=True):
            data = b"".join(self.disk[b].read() for b in self.disk[node.inode_block].pointers)
            print(f"Leitura concluída: {len(data)} bytes lidos dos blocos {self.disk[node.inode_block].pointers}.\n")

    def rm(self, path):
        print(f"> rm {path}")
        parent, name, node = self._resolve(path)
        if node and not node.is_dir and self._check_acl(node, path, 'w'):
            for b in self.disk[node.inode_block].pointers + [node.inode_block]:
                self.disk[b] = DiskBlock(b, self.block_size)
            del parent.children[name]

    def print_tree(self, node=None, prefix=""):
        if node is None:
            print("\n[ÁRVORE DO SISTEMA DE ARQUIVOS]\n/")
            node = self.root
        items = list(node.children.values())
        for i, child in enumerate(items):
            last = (i == len(items) - 1)
            conn = "└── " if last else "├── "
            if child.is_dir:
                print(f"{prefix}{conn}{child.name}/ [DIR]")
                self.print_tree(child, prefix + ("    " if last else "│   "))
            else:
                print(f"{prefix}{conn}{child.name} ({child.size // 1024} KB) [ARQ]")
        if node == self.root:
            print()

    def fs_status(self):
        print("> fs_status --details")
        print(f"Tamanho do Bloco de Disco: {self.block_size//1024} KB | Total de Blocos: {self.total_blocks} ({self.total_blocks*self.block_size//1024} KB)\n")
        print("[MAPA DE ALOCAÇÃO DO DISCO (Indexado)]")
        
        counts, frag_info = {}, {}
        for b in self.disk:
            if b.status.startswith("INODE"):
                print(f"Bloco {b.index:02d} [{b.status:<10}] : {b.owner}")
            elif b.status == "DADO":
                counts[b.owner] = counts.get(b.owner, 0) + 1
                print(f"Bloco {b.index:02d} [DADO]        : '{b.owner}' (Bloco {counts[b.owner]} - {b.used_bytes} bytes ocupados)")
                frag_info[b.owner] = (self.block_size - b.used_bytes, b.index)

        free = [b.index for b in self.disk if b.status == "LIVRE"]
        if free:
            print(f"Bloco {free[0]:02d}..{free[-1]:02d}           : [LIVRE]")

        print("\n--- RELATÓRIO DE FRAGMENTAÇÃO ---")
        for path, (frag, last_b) in frag_info.items():
            _, _, f = self._resolve(path)
            n_blocks = len(self.disk[f.inode_block].pointers)
            alloc = n_blocks * self.block_size
            print(f"Tamanho Real do Arquivo '{f.name}': {f.size} bytes ({f.size//1024} KB)")
            print(f"Espaço Alocado no Disco          : {alloc} bytes ({n_blocks} blocos de {self.block_size//1024} KB)")
            print(f"Fragmentação Interna             : {frag} bytes ({(frag/self.block_size)*100:.0f}% de desperdício no Bloco {last_b:02d})")
        print("Fragmentação Externa             : 0 bytes\nNecessidade de Compactação       : NÃO (Blocos alocados via i-node indexado)\n")

    # --- ETAPA 2: ESCALONAMENTO SSTF E RAID 5 REAL ---
    def write_file(self, path, text, custom_tracks=None):
        print(f'> write_file {path} "{text}"')
        _, _, node = self._resolve(path)
        if node and self._check_acl(node, path, 'w'):
            last_b = self.disk[node.inode_block].pointers[-1]
            self.disk[last_b].write(self.disk[last_b].read() + text.encode())
            self.io_queue.append(self.disk[last_b].track)

        reqs = custom_tracks if custom_tracks else self.io_queue
        print(f"[E/S] Requisições de leitura/escrita pendentes nas trilhas: {reqs}")
        print(f"Posição atual da cabeça de leitura: Trilha {self.head_pos}\n")
        print("--- ESCALONAMENTO DE DISCO: SSTF (Shortest Seek Time First) ---")

        curr, unvisited = self.head_pos, reqs.copy()
        order, movs, dists, total = [curr], [], [], 0
        while unvisited:
            nxt = min(unvisited, key=lambda x: abs(x - curr))
            d = abs(nxt - curr)
            movs.append(f"|{curr}-{nxt}|")
            dists.append(str(d))
            total += d
            curr = nxt
            unvisited.remove(nxt)
            order.append(curr)

        self.head_pos = curr
        self.io_queue.clear()
        print(f"Ordem de Atendimento : {' -> '.join(map(str, order))}")
        print(f"Deslocamento da Cabeça: {' + '.join(movs)}")
        print(f"Total de Movimento    : {' + '.join(dists)} = {total} trilhas\n")

    def write_raid5(self, path, size_kb):
        print(f"> write_file {path} --size {size_kb}")
        print("Arranjo Ativo: RAID 5 (3 Discos Físicos, Blocos de 4 KB)\n")
        
        part1 = (b"PLANILHA_PARTE_1_" * 256)[:self.block_size]
        part2 = (b"PLANILHA_PARTE_2_" * 256)[:self.block_size]
        parity = bytes(b1 ^ b2 for b1, b2 in zip(part1, part2))

        self.raid_disks[0][:] = part1
        self.raid_disks[1][:] = part2
        self.raid_disks[2][:] = parity

        name = path.split("/")[-1].split(".")[0].capitalize()
        print("[E/S - DISTRIBUIÇÃO EM DISCO]")
        print(f"Disco 1: [Bloco 01: Dados da {name} - Part 1 (4 KB)]")
        print(f"Disco 2: [Bloco 02: Dados da {name} - Part 2 (4 KB)]")
        print("Disco 3: [PARIDADE : XOR(Bloco 01, Bloco 02)]\n")

        print("[TESTE DE FALHA SIMULADO]")
        print("- Falha forçada no Disco 2!\n")
        self.raid_disks[1] = bytearray(self.block_size)

        recovered = bytes(b1 ^ bp for b1, bp in zip(self.raid_disks[0], self.raid_disks[2]))
        self.raid_disks[1][:] = recovered
        status = "OK" if recovered == part2 else "ERRO"
        print(f"- Recuperando Bloco 02 via operação XOR: (Disco 1 XOR Disco 3) -> Reconstrução [{status}]\n")

    # --- ETAPA 4: PROCESSOS E GERENCIAMENTO DE MEMÓRIA HÍBRIDA ---
    def create_process(self, name, size_kb, proc_type="normal"):
        size_val = int(str(size_kb).upper().replace("KB", ""))
        if proc_type == "critical":
            if self.mode != "MODO_KERNEL":
                print(f"[NEGADO] Processos críticos exigem MODO_KERNEL.\n")
                return
            print(f'> create_process --name "{name}" --size {size_val}KB --type critical')
            res = self.reserved_mem.allocate(name, size_val)
            if res:
                s_kb, e_kb = res
                print(f"- Alocado de forma contígua na Área Reservada: [{s_kb/1024:.1f} MB até {e_kb/1024:.1f} MB] ({size_val} KB)\n")
            else:
                print(f"[ERRO] Espaço contíguo insuficiente na Área Reservada para {size_val} KB.\n")
        else:
            self.virtual_mem.create_process(name, size_val)

    def terminate_process(self, name):
        print(f'> terminate_process --name "{name}"')
        res = self.reserved_mem.free(name)
        if res:
            s_kb, e_kb, size_val = res
            print(f"[ENCERRAMENTO DE PROCESSO CRÍTICO] Processo '{name}' finalizado.")
            print(f"Área de {size_val} KB no intervalo [{s_kb/1024:.1f} MB a {e_kb/1024:.1f} MB] liberada na Área Reservada da RAM.\n")


if __name__ == "__main__":
    fs = FileSystem(block_size=4096, total_blocks=16)

    # --- ETAPA 1 ---
    fs.mkdir("/sistema")
    fs.mkdir("/sistema/logs")
    fs.create("/sistema/logs/app.log", "10KB")
    fs.print_tree()
    fs.fs_status()

    # --- ETAPA 2 ---
    fs.write_file("/sistema/logs/app.log", "Novo Registro", custom_tracks=[98, 183, 37, 122, 14])
    fs.mkdir("/dados", silent=True)
    fs.write_raid5("/dados/planilha.csv", "8KB")

    # --- ETAPA 3 ---
    fs.create("/sistema/config.sys", "4KB", silent=True)
    fs.set_acl("/sistema/config.sys", "root", "admin", "750")

    fs.mkdir("/home", silent=True)
    fs.mkdir("/home/carlos", silent=True)
    fs.set_acl("/home/carlos", "carlos", "devs", "755")
    fs.create("/home/carlos/segredo.txt", "2KB", silent=True)
    fs.set_acl("/home/carlos/segredo.txt", "carlos", "devs", "700")

    fs.login("carlos", "senha123")
    fs.read_file("/sistema/config.sys")
    fs.encrypt_file("/home/carlos/segredo.txt", "MinhaChave123")

    bloco_alvo = fs.disk[fs.root.children["sistema"].children["logs"].children["app.log"].inode_block].pointers[0]
    fs.disk[bloco_alvo].data[:15] = b"DADO_CORROMPIDO"
    fs.antivirus_scan()

    # --- ETAPA 4: GERENCIAMENTO DE MEMÓRIA HÍBRIDA ---
    fs.login("root", "admin123")

    # Exemplo 4.1: Área Reservada (Alocação Contígua, Fragmentação Externa e Compactação)
    fs.create_process("Kernel_DiskDriver", "512KB", proc_type="critical")
    fs.create_process("Kernel_NetDriver", "1024KB", proc_type="critical")
    fs.create_process("Kernel_CryptoEngine", "512KB", proc_type="critical")
    fs.terminate_process("Kernel_NetDriver")
    fs.reserved_mem.status()
    fs.reserved_mem.compact()

    # Exemplo 4.2: Área de Memória Virtual (Paginação, Fragmentação Interna e LRU)
    fs.create_process("App_Navegador", "10KB", proc_type="normal")
    fs.virtual_mem.map_page_direct("App_Navegador", page_num=1, frame_id=12, age_ms=5)
    fs.virtual_mem.fill_remaining_frames_for_pressure(holder_proc="Bg_Service", holder_pid=102)

    fs.virtual_mem.translate_address("App_Navegador", page_num=1)
    fs.virtual_mem.access_page("App_Navegador", page_num=2, instruction="LOAD_DATA Página 2")
    fs.virtual_mem.memory_summary()