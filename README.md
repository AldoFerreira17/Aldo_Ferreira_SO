# Simulador de Sistema de Arquivos e Gerenciamento de Memória (SO)

**Autor:** Aldo Ferreira  
**Instituição:** Universidade Federal Rural de Pernambuco (UFRPE)  
**Disciplina:** Sistemas Operacionais  

Este projeto implementa um Simulador de Sistema de Arquivos e Memória Híbrida em Python (`main.py`), integrando alocação física em blocos, escalonamento de disco, tolerância a falhas RAID 5, segurança/ACL e gerenciamento de memória física e virtual.

---

## Funcionalidades Implementadas

### Etapa 1: Hierarquia em Árvore, CRUD e Alocação Física (i-node)
* **Navegação:** Suporte a caminhos absolutos e relativos (`.` e `..`).
* **Operações CRUD:** `mkdir`, `create`, `read_file`, `write_file` e `rm` operando sobre blocos físicos (`bytearray(4096)`).
* **Alocação Indexada (i-node):** Tabela de ponteiros em bloco dedicado e cálculo dinâmico de fragmentação interna.

### Etapa 2: Subsistema de E/S, Escalonamento SSTF e RAID 5
* **Escalonamento SSTF:** Ordenação da fila de trilhas pelo menor tempo de busca (*Shortest Seek Time First*).
* **RAID 5 Real:** Particionamento em 3 discos físicos, cálculo matemático de paridade bit a bit (`XOR`), falha física forçada e reconstrução real dos bytes via `XOR` dos discos sobreviventes.

### Etapa 3: Segurança, ACL, Criptografia e Antivírus
* **Modos e Autenticação:** Alternância entre `MODO_KERNEL` (`root`) e `MODO_USUARIO`, com senhas armazenadas em hash `SHA-256` + *Salt*.
* **Controle de Acesso (ACL):** Verificação de permissões octais (`rwx`) para Proprietário, Grupo e Outros.
* **Criptografia e Integridade:** Cifra `XOR` aplicada diretamente sobre os bytes dos blocos físicos e varredura de integridade que recalcula o hash `SHA-256` real de cada bloco para acusar adulterações.

### Etapa 4: Gerenciamento de Memória Híbrida (Contígua + Paginada)
* **Região Estática/Reservada (`ReservedMemory`):** Alocação contígua (*First-Fit*) de 4 MB exclusiva para o Kernel e drivers críticos, com diagnóstico de fragmentação externa e rotina real de **compactação** de endereços base.
* **Região Dinâmica Virtual (`VirtualMemoryManager`):** Gerenciamento por paginação (páginas de 4 KB) para processos comuns, cálculo de fragmentação interna, tradução de endereço lógico para moldura física e tratamento de **Page Fault** com swapping real para disco usando o algoritmo **LRU (*Least Recently Used*)**.

---

## Como Executar

```bash
git clone [https://github.com/AldoFerreira17/Aldo_Ferreira_SO.git](https://github.com/AldoFerreira17/Aldo_Ferreira_SO.git)
cd Aldo_Ferreira_SO
python main.py