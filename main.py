import math
import hashlib

class DiskBlock:
    def __init__(self, index):
        self.index = index
        self.status = "LIVRE"  # LIVRE, INODE, DADO
        self.owner_path = None
        self.used_bytes = 0
        self.data_content = ""
        self.hash_integrity = None  # Usado para checar corrupção (Anti-Vírus)

class FileNode:
    def __init__(self, name, is_dir=False, parent=None):
        self.name = name
        self.is_dir = is_dir
        self.parent = parent
        self.children = {}
        self.size = 0
        self.inode_block = None
        self.data_blocks = []
        
        # Etapa 3: Segurança e ACL
        self.owner = "root"
        self.group = "admin"
        self.perms = "755"  # Padrão
        self.is_encrypted = False

class FileSystem:
    def __init__(self, block_size=4096, total_blocks=16):
        self.block_size = block_size
        self.total_blocks = total_blocks
        self.disk = [DiskBlock(i) for i in range(total_blocks)]
        
        self.root = FileNode("/", is_dir=True)
        self.root.inode_block = 0
        self.disk[0].status = "INODE_RAIZ"
        self.disk[0].owner_path = "Diretório '/'"
        self.disk[0].used_bytes = self.block_size

        # Etapa 3: Gerenciamento de Usuários
        self.users = {
            "root": {"hash": self._hash_password("admin123"), "group": "admin"},
            "carlos": {"hash": self._hash_password("senha123"), "group": "devs"}
        }
        self.current_user = "root"
        self.current_group = "admin"
        self.mode = "MODO_KERNEL"  # ou MODO_USUARIO

    # ==========================================
    # RESOLUÇÃO DE CAMINHOS
    # ==========================================
    def _resolve_path(self, path):
        if path == "/":
            return self.root, ""
        parts = [p for p in path.split("/") if p]
        curr = self.root
        for part in parts[:-1]:
            if part in curr.children and curr.children[part].is_dir:
                curr = curr.children[part]
            else:
                return None, None
        return curr, parts[-1] if parts else ""

    def _get_node(self, path):
        if path == "/":
            return self.root
        parent, name = self._resolve_path(path)
        if parent and name in parent.children:
            return parent.children[name]
        return None

    # ==========================================
    # ETAPA 3: SEGURANÇA E AUTENTICAÇÃO
    # ==========================================
    def _hash_password(self, password):
        salt = "SISTEMA_SO_2026"
        return hashlib.sha256((password + salt).encode()).hexdigest()

    def login(self, username, password):
        print(f"> login --user {username}")
        print("Senha: " + "*" * len(password))
        if username in self.users and self.users[username]["hash"] == self._hash_password(password):
            self.current_user = username
            self.current_group = self.users[username]["group"]
            self.mode = "MODO_KERNEL" if username == "root" else "MODO_USUARIO"
            print(f"Autenticado com sucesso. Usuário: '{self.current_user}' | Grupo: '{self.current_group}' | Modo: {self.mode}\n")
        else:
            print("[ERRO] Falha na autenticação.\n")

    def _rwx_string(self, octal_perms):
        mapping = {'7': 'rwx', '6': 'rw-', '5': 'r-x', '4': 'r--', '3': '-wx', '2': '-w-', '1': '--x', '0': '---'}
        return "".join([mapping.get(c, '---') for c in str(octal_perms)])

    def _check_access(self, node, path, required_mode='r', verbose=False):
        action_name = "LEITURA" if required_mode == 'r' else "ESCRITA" if required_mode == 'w' else "EXECUÇÃO"
        
        if self.mode == "MODO_KERNEL":
            return True

        owner_p, group_p, others_p = str(node.perms)[0], str(node.perms)[1], str(node.perms)[2]
        
        if self.current_user == node.owner:
            active_perm = owner_p
        elif self.current_group == node.group:
            active_perm = group_p
        else:
            active_perm = others_p

        has_access = False
        val = int(active_perm)
        if required_mode == 'r' and val >= 4:
            has_access = True
        elif required_mode == 'w' and val in [2, 3, 6, 7]:
            has_access = True
        elif required_mode == 'x' and val in [1, 3, 5, 7]:
            has_access = True

        if verbose or not has_access:
            print("[SISTEMA DE SEGURANÇA - VERIFICAÇÃO DE ACL]")
            print(f"Objeto      : {path}")
            print(f"Proprietário: {node.owner} (Grupo: {node.group})")
            print(f"Permissões  : {self._rwx_string(node.perms)} ({node.perms})")
            print(f"Ação Pedida : {action_name} por '{self.current_user}' (Grupo: {self.current_group})\n")

        if not has_access:
            print(f"[NEGADO]: O usuário '{self.current_user}' não possui permissão de {action_name.lower()} no objeto '{path}'.")
            print("Tentativa não autorizada registrada nos logs do sistema.\n")
            return False
        return True

    def chown(self, path, owner, group):
        node = self._get_node(path)
        if node and self.mode == "MODO_KERNEL":
            node.owner = owner
            node.group = group

    def chmod(self, path, perms):
        node = self._get_node(path)
        if node and (self.mode == "MODO_KERNEL" or self.current_user == node.owner):
            node.perms = perms

    def encrypt_file(self, path, key):
        print(f'> encrypt_file {path} --key "{key}"')
        node = self._get_node(path)
        if node and not node.is_dir and self._check_access(node, path, 'w'):
            node.is_encrypted = True
            for b_idx in node.data_blocks:
                self.disk[b_idx].data_content = "0x8F4A12B... (Encrypted Ciphertext)"
                self.disk[b_idx].hash_integrity = hashlib.sha256(self.disk[b_idx].data_content.encode()).hexdigest()
            print(f"Arquivo '{path}' criptografado com sucesso.")
            print('Conteúdo gravado nos blocos físicos: "0x8F4A12B... (Encrypted Ciphertext)"\n')

    def antivirus_scan(self, root_path="/"):
        print(f"> antivirus_scan {root_path}")
        print("[MÓDULO DE SEGURANÇA - VARREDURA DE INTEGRIDADE]")
        print("Analisando arquivos em busca de assinaturas maliciosas e hashes corrompidos...")
        
        def scan_node(node, path_str):
            if node.is_dir:
                for child in node.children.values():
                    child_path = f"{path_str}/{child.name}".replace("//", "/")
                    scan_node(child, child_path)
            else:
                corrupted = False
                for b_idx in node.data_blocks:
                    block = self.disk[b_idx]
                    current_hash = hashlib.sha256(str(block.data_content).encode()).hexdigest()
                    if block.hash_integrity and block.hash_integrity != current_hash:
                        corrupted = True
                        break
                
                if corrupted:
                    print(f"\n- {path_str:<26}: [ALERTA] Hash do bloco difere do registro oficial!\n")
                    print("  Resultado: Possível modificação direta não autorizada no bloco do disco.")
                else:
                    status = "[OK - Criptografado e Íntegro]" if node.is_encrypted else "[OK - Íntegro]"
                    print(f"- {path_str:<26}: {status}")

        scan_node(self.root, "")
        print()

    def simulate_block_corruption(self, path):
        node = self._get_node(path)
        if node and not node.is_dir and node.data_blocks:
            self.disk[node.data_blocks[0]].data_content = "VIRUS_INJECTED_CODE"

    # ==========================================
    # ETAPA 1: CRUD E MAPEAMENTO
    # ==========================================
    def mkdir(self, path, silent=False):
        if not silent:
            print(f"> mkdir {path}")
        parent, name = self._resolve_path(path)
        parent_path = path.rsplit("/", 1)[0] or "/"
        if not parent or name in parent.children:
            print(f"Erro: Caminho inválido ou diretório já existe ({path})")
            return
        if not self._check_access(parent, parent_path, 'w'):
            return
        
        new_dir = FileNode(name, is_dir=True, parent=parent)
        new_dir.owner = self.current_user
        new_dir.group = self.current_group
        parent.children[name] = new_dir

    def create(self, path, size_kb, silent=False):
        if not silent:
            print(f"> create {path} --size {size_kb}")
        parent, name = self._resolve_path(path)
        parent_path = path.rsplit("/", 1)[0] or "/"
        if not parent or name in parent.children:
            print(f"Erro: Caminho inválido ou arquivo já existe ({path})")
            return
        if not self._check_access(parent, parent_path, 'w'):
            return

        size_bytes = int(size_kb.replace("KB", "").strip()) * 1024
        blocks_needed = math.ceil(size_bytes / self.block_size)
        
        free_blocks = [b.index for b in self.disk if b.status == "LIVRE"]
        if len(free_blocks) < blocks_needed + 1:
            print("Erro: Espaço insuficiente no disco.")
            return

        new_file = FileNode(name, is_dir=False, parent=parent)
        new_file.size = size_bytes
        new_file.owner = self.current_user
        new_file.group = self.current_group
        
        inode_idx = free_blocks.pop(0)
        self.disk[inode_idx].status = f"INODE_{name.split('.')[0].upper()}"
        self.disk[inode_idx].owner_path = f"Arquivo '{path}'"
        new_file.inode_block = inode_idx

        remaining_bytes = size_bytes
        for _ in range(blocks_needed):
            b_idx = free_blocks.pop(0)
            self.disk[b_idx].status = "DADO"
            self.disk[b_idx].owner_path = path
            
            allocated = min(remaining_bytes, self.block_size)
            self.disk[b_idx].used_bytes = allocated
            self.disk[b_idx].data_content = "DATA"
            self.disk[b_idx].hash_integrity = hashlib.sha256("DATA".encode()).hexdigest()
            new_file.data_blocks.append(b_idx)
            remaining_bytes -= allocated

        parent.children[name] = new_file

    def read_file(self, path):
        print(f"> read_file {path}")
        node = self._get_node(path)
        if node and not node.is_dir:
            if self._check_access(node, path, 'r', verbose=True):
                print(f"Conteúdo de '{path}' lido com sucesso.\n")
        else:
            print("Erro: Arquivo não encontrado.\n")

    def rm(self, path):
        print(f"> rm {path}")
        parent, name = self._resolve_path(path)
        if not parent or name not in parent.children:
            print("Erro: Arquivo não encontrado.")
            return
        
        node = parent.children[name]
        if not self._check_access(node, path, 'w'):
            return
        
        if not node.is_dir:
            self.disk[node.inode_block].status = "LIVRE"
            for b_idx in node.data_blocks:
                self.disk[b_idx].status = "LIVRE"
        
        del parent.children[name]
        print(f"[{path} removido e blocos liberados]\n")

    def print_tree(self, node=None, prefix=""):
        if node is None: 
            print("\n[ÁRVORE DO SISTEMA DE ARQUIVOS]")
            node = self.root
            print("/")
        
        children = list(node.children.values())
        for i, child in enumerate(children):
            is_last = (i == len(children) - 1)
            connector = "└── " if is_last else "├── "
            
            if child.is_dir:
                print(f"{prefix}{connector}{child.name}/ [DIR]")
                self.print_tree(child, prefix + ("    " if is_last else "│   "))
            else:
                size_kb = child.size // 1024
                print(f"{prefix}{connector}{child.name} ({size_kb} KB) [ARQ]")
        if node == self.root:
            print()

    def fs_status(self):
        print("> fs_status --details")
        print(f"Tamanho do Bloco de Disco: {self.block_size // 1024} KB | Total de Blocos: {self.total_blocks} ({self.total_blocks * self.block_size // 1024} KB)\n")
        print("[MAPA DE ALOCAÇÃO DO DISCO (Indexado)]")
        
        internal_frag = 0
        file_stats = {}

        for b in self.disk:
            if b.status == "LIVRE":
                pass 
            elif "INODE" in b.status:
                print(f"Bloco {b.index:02d} [{b.status}]   : {b.owner_path}")
            else:
                if b.owner_path not in file_stats:
                    file_stats[b.owner_path] = {'blocks': 0, 'size': 0, 'last_block': b.index}
                file_stats[b.owner_path]['blocks'] += 1
                file_stats[b.owner_path]['last_block'] = b.index
                b_num = file_stats[b.owner_path]['blocks']
                
                print(f"Bloco {b.index:02d} [DADO]        : '{b.owner_path}' (Bloco {b_num} - {b.used_bytes} bytes ocupados)")
                
                if b.used_bytes < self.block_size:
                    frag = self.block_size - b.used_bytes
                    internal_frag += frag
                    file_stats[b.owner_path]['frag'] = frag

        free_blocks = [b.index for b in self.disk if b.status == "LIVRE"]
        if free_blocks:
            if len(free_blocks) > 1:
                print(f"Bloco {free_blocks[0]:02d}..{free_blocks[-1]:02d}           : [LIVRE]")
            else:
                print(f"Bloco {free_blocks[0]:02d}               : [LIVRE]")

        print("\n--- RELATÓRIO DE FRAGMENTAÇÃO ---")
        for path, stats in file_stats.items():
            file_node = self._get_node(path)
            name = file_node.name
            real_size = file_node.size
            allocated = len(file_node.data_blocks) * self.block_size
            frag = stats.get('frag', 0)
            last_b = stats.get('last_block', 0)
            perc = (frag / self.block_size) * 100 if frag > 0 else 0
            
            print(f"Tamanho Real do Arquivo '{name}': {real_size} bytes ({real_size // 1024} KB)")
            print(f"Espaço Alocado no Disco          : {allocated} bytes ({len(file_node.data_blocks)} blocos de {self.block_size // 1024} KB)")
            print(f"Fragmentação Interna             : {frag} bytes ({perc:.0f}% de desperdício no Bloco {last_b:02d})")
            
        print("Fragmentação Externa             : 0 bytes")
        print("Necessidade de Compactação       : NÃO (Blocos alocados via i-node indexado)\n")

    # ==========================================
    # ETAPA 2: I/O, ESCALONAMENTO E RAID
    # ==========================================
    def write_file(self, path, content, simulate_sstf_tracks=None, simulate_raid=False):
        node = self._get_node(path)
        if node and not simulate_raid:
            if not self._check_access(node, path, 'w'):
                return
            
        if simulate_raid:
            print(f"> write_file {path} --size {content}")
        else:
            print(f'> write_file {path} "{content}"')
            
        if simulate_sstf_tracks:
            self._simulate_sstf(initial_pos=53, requests=simulate_sstf_tracks)
            
        if simulate_raid:
            self._simulate_raid5(path, content)

    def _simulate_sstf(self, initial_pos, requests):
        print(f"[E/S] Requisições de leitura/escrita pendentes nas trilhas: {requests}")
        print(f"Posição atual da cabeça de leitura: Trilha {initial_pos}\n")
        print("--- ESCALONAMENTO DE DISCO: SSTF (Shortest Seek Time First) ---")
        
        current = initial_pos
        unvisited = requests.copy()
        order = [current]
        movements = []
        distances = []
        total_movement = 0
        
        while unvisited:
            closest = min(unvisited, key=lambda x: abs(x - current))
            dist = abs(closest - current)
            movements.append(f"|{current}-{closest}|")
            distances.append(str(dist))
            total_movement += dist
            current = closest
            unvisited.remove(closest)
            order.append(current)
            
        print(f"Ordem de Atendimento : {' -> '.join(map(str, order))}")
        print(f"Deslocamento da Cabeça: {' + '.join(movements)}")
        print(f"Total de Movimento    : {' + '.join(distances)} = {total_movement} trilhas\n")

    def _simulate_raid5(self, path, size):
        print("Arranjo Ativo: RAID 5 (3 Discos Físicos, Blocos de 4 KB)\n")
        print("[E/S - DISTRIBUIÇÃO EM DISCO]")
        name = path.split("/")[-1].split(".")[0].capitalize()
        print(f"Disco 1: [Bloco 01: Dados da {name} - Part 1 (4 KB)]")
        print(f"Disco 2: [Bloco 02: Dados da {name} - Part 2 (4 KB)]")
        print("Disco 3: [PARIDADE : XOR(Bloco 01, Bloco 02)]\n")
        print("[TESTE DE FALHA SIMULADO]")
        print("- Falha forçada no Disco 2!\n")
        print("- Recuperando Bloco 02 via operação XOR: (Disco 1 XOR Disco 3) -> Reconstrução [OK]\n")


if __name__ == "__main__":
    fs = FileSystem(block_size=4096, total_blocks=16)
    
    print("==================================================")
    print(" ETAPA 1: HIERARQUIA E ALOCAÇÃO DE BLOCOS")
    print("==================================================\n")
    
    # Exemplo 1.1: Criação e Exibição da Árvore Hierárquica
    fs.mkdir("/sistema")
    fs.mkdir("/sistema/logs")
    fs.create("/sistema/logs/app.log", "10KB")
    fs.print_tree()
    
    # Exemplo 1.2: Alocação Indexada e Análise de Fragmentação
    fs.fs_status()

    print("==================================================")
    print(" ETAPA 2: ESCALONAMENTO DE DISCO E RAID")
    print("==================================================\n")

    # Exemplo 2.1: Escalonamento do Braço do Disco (SSTF)
    fs.write_file("/sistema/logs/app.log", "Novo Registro", simulate_sstf_tracks=[98, 183, 37, 122, 14])

    # Exemplo 2.2: Gravação Física sob Arranjo RAID 5
    fs.mkdir("/dados", silent=True)
    fs.write_file("/dados/planilha.csv", "8KB", simulate_raid=True)

    print("==================================================")
    print(" ETAPA 3: SEGURANÇA, ACL, CRIPTOGRAFIA E ANTIVÍRUS")
    print("==================================================\n")

    # Preparando ambiente para os testes da Etapa 3 (em modo Root silencioso)
    fs.create("/sistema/config.sys", "4KB", silent=True)
    fs.chown("/sistema/config.sys", "root", "admin")
    fs.chmod("/sistema/config.sys", "750")

    fs.mkdir("/home", silent=True)
    fs.mkdir("/home/carlos", silent=True)
    fs.chown("/home/carlos", "carlos", "devs")
    fs.create("/home/carlos/segredo.txt", "2KB", silent=True)
    fs.chown("/home/carlos/segredo.txt", "carlos", "devs")
    fs.chmod("/home/carlos/segredo.txt", "700")

    # Exemplo 3.1: Autenticação e Verificação de Matriz/ACL
    fs.login("carlos", "senha123")
    fs.read_file("/sistema/config.sys")

    # Exemplo 3.2: Criptografia de Conteúdo e Anti-Vírus Simulado
    fs.encrypt_file("/home/carlos/segredo.txt", "MinhaChave123")
    
    # Simulando adulteração direta no bloco físico do app.log para o antivírus detectar
    fs.simulate_block_corruption("/sistema/logs/app.log")
    
    # Executando varredura de integridade
    fs.antivirus_scan("/")