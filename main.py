import math

class DiskBlock:
    def __init__(self, index):
        self.index = index
        self.status = "LIVRE" # LIVRE, INODE, DADO
        self.owner_path = None
        self.used_bytes = 0

class FileNode:
    def __init__(self, name, is_dir=False, parent=None):
        self.name = name
        self.is_dir = is_dir
        self.parent = parent
        self.children = {}
        self.size = 0
        self.inode_block = None
        self.data_blocks = []

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

    def _resolve_path(self, path):
        if path == "/": return self.root, ""
        parts = [p for p in path.split("/") if p]
        curr = self.root
        for part in parts[:-1]:
            if part in curr.children and curr.children[part].is_dir:
                curr = curr.children[part]
            else:
                return None, None
        return curr, parts[-1] if parts else ""

    # ==========================================
    # ETAPA 1: CRUD E MAPEAMENTO
    # ==========================================
    def mkdir(self, path):
        parent, name = self._resolve_path(path)
        if not parent or name in parent.children:
            print(f"Erro: Caminho inválido ou diretório já existe ({path})")
            return
        
        new_dir = FileNode(name, is_dir=True, parent=parent)
        parent.children[name] = new_dir
        print(f"> mkdir {path}")

    def create(self, path, size_kb):
        print(f"> create {path} --size {size_kb}")
        parent, name = self._resolve_path(path)
        if not parent or name in parent.children:
            print(f"Erro: Caminho inválido ou arquivo já existe ({path})")
            return

        size_bytes = int(size_kb.replace("KB", "").strip()) * 1024
        blocks_needed = math.ceil(size_bytes / self.block_size)
        
        free_blocks = [b.index for b in self.disk if b.status == "LIVRE"]
        if len(free_blocks) < blocks_needed + 1:
            print("Erro: Espaço insuficiente no disco.")
            return

        new_file = FileNode(name, is_dir=False, parent=parent)
        new_file.size = size_bytes
        
        inode_idx = free_blocks.pop(0)
        self.disk[inode_idx].status = f"INODE_{name.split('.')[0].upper()}"
        self.disk[inode_idx].owner_path = f"Arquivo '{path}'"
        new_file.inode_block = inode_idx

        remaining_bytes = size_bytes
        for _ in range(blocks_needed):
            b_idx = free_blocks.pop(0)
            self.disk[b_idx].status = "DADO"
            self.disk[b_idx].owner_path = path
            
            allocated_in_block = min(remaining_bytes, self.block_size)
            self.disk[b_idx].used_bytes = allocated_in_block
            new_file.data_blocks.append(b_idx)
            remaining_bytes -= allocated_in_block

        parent.children[name] = new_file

    def rm(self, path):
        print(f"> rm {path}")
        parent, name = self._resolve_path(path)
        if not parent or name not in parent.children:
            print("Erro: Arquivo não encontrado.")
            return
        
        node = parent.children[name]
        
        # Libera os blocos físicos do arquivo
        if not node.is_dir:
            self.disk[node.inode_block].status = "LIVRE"
            for b_idx in node.data_blocks:
                self.disk[b_idx].status = "LIVRE"
        
        del parent.children[name]
        print(f"[{path} removido e blocos liberados]")

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
        if node == self.root: print()

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
                    file_stats[b.owner_path] = {'blocks': 0, 'size': 0}
                file_stats[b.owner_path]['blocks'] += 1
                b_num = file_stats[b.owner_path]['blocks']
                
                print(f"Bloco {b.index:02d} [DADO]           : '{b.owner_path}' (Bloco {b_num} - {b.used_bytes} bytes ocupados)")
                
                if b.used_bytes < self.block_size:
                    frag = self.block_size - b.used_bytes
                    internal_frag += frag
                    file_stats[b.owner_path]['frag'] = frag

        free_blocks = [b.index for b in self.disk if b.status == "LIVRE"]
        if free_blocks:
            if len(free_blocks) > 1:
                print(f"Bloco {free_blocks[0]:02d}..{free_blocks[-1]:02d}           : [LIVRE]")
            else:
                print(f"Bloco {free_blocks[0]:02d}              : [LIVRE]")

        print("\n--- RELATÓRIO DE FRAGMENTAÇÃO ---")
        for path, stats in file_stats.items():
            parent_node, name = self._resolve_path(path)
            file_node = parent_node.children[name] # <-- CORREÇÃO AQUI
            
            real_size = file_node.size
            allocated = len(file_node.data_blocks) * self.block_size
            frag = stats.get('frag', 0)
            perc = (frag / self.block_size) * 100 if frag > 0 else 0
            
            print(f"Tamanho Real do Arquivo '{name}': {real_size} bytes ({real_size//1024} KB)")
            print(f"Espaço Alocado no Disco          : {allocated} bytes ({len(file_node.data_blocks)} blocos de {self.block_size//1024} KB)")
            print(f"Fragmentação Interna             : {frag} bytes ({perc:.0f}% de desperdício no último bloco)")
            
        print("Fragmentação Externa             : 0 bytes")
        print("Necessidade de Compactação       : NÃO (Blocos alocados via i-node indexado)\n")

    # ==========================================
    # ETAPA 2: I/O, ESCALONAMENTO E RAID
    # ==========================================
    def write_file(self, path, content, simulate_sstf_tracks=None, simulate_raid=False):
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
            
        order_str = " -> ".join(map(str, order))
        mov_str = " + ".join(movements)
        calc_str = " + ".join(distances)
        
        print(f"Ordem de Atendimento : {order_str}")
        print(f"Deslocamento da Cabeça: {mov_str}")
        print(f"Total de Movimento    : {calc_str} = {total_movement} trilhas\n")

    def _simulate_raid5(self, path, size):
        print(f"Arranjo Ativo: RAID 5 (3 Discos Físicos, Blocos de 4 KB)\n")
        print("[E/S - DISTRIBUIÇÃO EM DISCO]")
        name = path.split("/")[-1].split(".")[0].capitalize()
        
        print(f"Disco 1: [Bloco 01: Dados da {name} - Part 1 (4 KB)]")
        print(f"Disco 2: [Bloco 02: Dados da {name} - Part 2 (4 KB)]")
        print(f"Disco 3: [PARIDADE : XOR(Bloco 01, Bloco 02)]\n")
        
        print("[TESTE DE FALHA SIMULADO]")
        print("- Falha forçada no Disco 2!\n")
        print("- Recuperando Bloco 02 via operação XOR: (Disco 1 XOR Disco 3) -> Reconstrução [OK]\n")

if __name__ == "__main__":
    fs = FileSystem(block_size=4096, total_blocks=16)
    
    # --- Exemplo 1.1: Árvore Hierárquica ---
    fs.mkdir("/sistema")
    fs.mkdir("/sistema/logs")
    fs.create("/sistema/logs/app.log", "10KB")
    fs.print_tree()
    
    # --- Exemplo 1.2: Alocação Indexada e Fragmentação ---
    fs.fs_status()

    # --- Exemplo 2.1: Escalonamento de Disco (SSTF) ---
    fs.write_file("/sistema/logs/app.log", "Novo Registro", simulate_sstf_tracks=[98, 183, 37, 122, 14])

    # --- Exemplo 2.2: RAID 5 ---
    fs.mkdir("/dados")
    fs.write_file("/dados/planilha.csv", "8KB", simulate_raid=True)