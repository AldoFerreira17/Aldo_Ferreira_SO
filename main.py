import math
from datetime import datetime

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

    def mkdir(self, path):
        parent, name = self._resolve_path(path)
        if not parent or name in parent.children:
            print(f"Erro: Caminho inválido ou diretório já existe ({path})")
            return
        
        new_dir = FileNode(name, is_dir=True, parent=parent)
        parent.children[name] = new_dir
        print(f"Diretório criado: {path}")

    def create(self, path, size_kb):
        parent, name = self._resolve_path(path)
        if not parent or name in parent.children:
            print(f"Erro: Caminho inválido ou arquivo já existe ({path})")
            return

        size_bytes = int(size_kb.replace("KB", "").strip()) * 1024
        blocks_needed = math.ceil(size_bytes / self.block_size)
        
        # Procura blocos livres (1 para Inode + N para dados)
        free_blocks = [b.index for b in self.disk if b.status == "LIVRE"]
        if len(free_blocks) < blocks_needed + 1:
            print("Erro: Espaço insuficiente no disco.")
            return

        new_file = FileNode(name, is_dir=False, parent=parent)
        new_file.size = size_bytes
        
        # Aloca INODE
        inode_idx = free_blocks.pop(0)
        self.disk[inode_idx].status = f"INODE_{name.split('.')[0].upper()}"
        self.disk[inode_idx].owner_path = f"Arquivo '{path}'"
        new_file.inode_block = inode_idx

        # Aloca DADOS
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
        print(f"Arquivo criado: {path} ({size_kb})")

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

    def fs_status(self):
        print(f"\nTamanho do Bloco de Disco: {self.block_size // 1024} KB | Total de Blocos: {self.total_blocks} ({self.total_blocks * self.block_size // 1024} KB)\n")
        print("[MAPA DE ALOCAÇÃO DO DISCO (Indexado)]")
        
        internal_frag = 0
        file_stats = {}

        for b in self.disk:
            if b.status == "LIVRE":
                print(f"Bloco {b.index:02d}           : [LIVRE]")
            elif "INODE" in b.status:
                print(f"Bloco {b.index:02d} [{b.status}]  : {b.owner_path}")
            else:
                # É um bloco de dado
                if b.owner_path not in file_stats:
                    file_stats[b.owner_path] = {'blocks': 0, 'size': 0}
                file_stats[b.owner_path]['blocks'] += 1
                b_num = file_stats[b.owner_path]['blocks']
                
                print(f"Bloco {b.index:02d} [DADO]      : '{b.owner_path}' (Bloco {b_num} - {b.used_bytes} bytes ocupados)")
                
                # Calcula fragmentação interna se for o último bloco que não ocupa tudo
                if b.used_bytes < self.block_size:
                    frag = self.block_size - b.used_bytes
                    internal_frag += frag
                    file_stats[b.owner_path]['frag'] = frag

        print("\n--- RELATÓRIO DE FRAGMENTAÇÃO ---")
        for path, stats in file_stats.items():
            node, name = self._resolve_path(path)
            real_size = node.size
            allocated = len(node.data_blocks) * self.block_size
            frag = stats.get('frag', 0)
            perc = (frag / self.block_size) * 100 if frag > 0 else 0
            
            print(f"Tamanho Real do Arquivo '{name}': {real_size} bytes ({real_size//1024} KB)")
            print(f"Espaço Alocado no Disco          : {allocated} bytes ({len(node.data_blocks)} blocos de {self.block_size//1024} KB)")
            print(f"Fragmentação Interna             : {frag} bytes ({perc:.0f}% de desperdício no último bloco)")
            
        print("Fragmentação Externa             : 0 bytes (Alocação indexada não sofre de fragmentação externa)")
        print("Necessidade de Compactação       : NÃO (Blocos alocados via i-node indexado)")


if __name__ == "__main__":
    fs = FileSystem(block_size=4096, total_blocks=16)
    
    # Simulando os comandos exigidos no exemplo
    print("> mkdir /sistema")
    fs.mkdir("/sistema")
    
    print("> mkdir /sistema/logs")
    fs.mkdir("/sistema/logs")
    
    print("> create /sistema/logs/app.log --size 10KB")
    fs.create("/sistema/logs/app.log", "10KB")
    
    fs.print_tree()
    fs.fs_status()