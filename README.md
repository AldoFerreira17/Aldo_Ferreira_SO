# Simulador de Sistema de Arquivos (SO)

**Autor:** Aldo Ferreira  
**Instituição:** Universidade Federal Rural de Pernambuco (UFRPE)  
**Disciplina:** Sistemas Operacionais  

Este projeto implementa um Simulador de Sistema de Arquivos em Python, englobando alocação física, escalonamento de disco, tolerância a falhas e mecanismos de segurança.

## Funcionalidades Implementadas

### Etapa 1: Organização e Mapeamento
- **Hierarquia:** Estrutura em árvore de diretórios e arquivos absolutos.
- **CRUD:** `mkdir`, `create`, `rm`, `read_file`, `write_file`.
- **Alocação:** Indexada via blocos físicos de disco (i-node).
- **Diagnóstico:** Cálculo matemático de fragmentação interna e relatório de disco.

### Etapa 2: Escalonamento e RAID
- **I/O e Escalonamento:** Simulação do algoritmo SSTF (*Shortest Seek Time First*) com cálculo de trilhas.
- **Tolerância a Falhas:** Abstração de arranjo RAID 5 (distribuição de dados e recuperação via cálculo de paridade XOR).

### Etapa 3: Segurança e Integridade
- **Modos de Execução:** Alternância entre Modo Kernel (Superusuário/Root) e Modo Usuário.
- **Autenticação:** Sistema de Login, Usuários e Grupos com hashing de senhas `SHA-256` com Salt.
- **Controle de Acesso:** Verificação via ACL baseada em `rwx` e formato octal (ex: `750`).
- **Criptografia:** Simulação de dados cifrados no bloco físico em repouso.
- **Anti-Vírus (Integridade):** Scanner de blocos físicos que acusa alterações não autorizadas baseando-se na divergência da assinatura em hash (`SHA-256`) do bloco.
