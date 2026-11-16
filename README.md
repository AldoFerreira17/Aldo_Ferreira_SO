# Simulador de Sistema de Arquivos (SO)

**Autor:** Aldo Ferreira  
**Instituição:** Universidade Federal Rural de Pernambuco (UFRPE)  
**Disciplina:** Sistemas Operacionais  

Este projeto implementa um Simulador de Sistema de Arquivos completo em Python (`main.py`), integrando gerenciamento de diretórios, alocação física real em blocos de memória, escalonamento de braço de disco, redundância RAID 5 e mecanismos de segurança e auditoria de integridade.

---

## Arquitetura e Implementação Algorítmica

Diferente de simulações estáticas, este projeto manipula estruturas de dados e vetores de bytes reais (`bytearray`) em todas as camadas:

### Etapa 1: Hierarquia em Árvore, CRUD e Alocação Física (i-node)
* **Estrutura Navegável (`FileNode`):** Suporte completo a caminhos absolutos (`/sistema/logs`) e relativos (`.` e `..`) através do método de resolução de árvore `_resolve()`.
* **Operações CRUD:** 
  * `mkdir` e `create`: Instanciam nós na árvore e alocam blocos físicos reais.
  * `read_file`: Percorre a tabela de ponteiros do `i-node` do arquivo e reconstrói o conteúdo lendo os bytes diretamente dos blocos físicos de dados.
  * `write_file`: Anexa novos bytes ao último bloco físico do arquivo e gera requisições reais de cilindro/trilha na fila de E/S.
  * `rm`: Limpa os vetores de bytes dos blocos de dados e do bloco de `i-node`, restituindo o status `LIVRE`.
* **Camada Física (`DiskBlock`):** O disco é dividido em 16 blocos físicos de `4096 bytes` (4 KB) cada, utilizando `bytearray(4096)` em memória. Na **Alocação Indexada (i-node)**, um bloco físico armazena a tabela de ponteiros (`pointers`) e os demais armazenam as fatias de bytes reais do arquivo.
* **Diagnóstico e Fragmentação (`fs_status`):** Analisa dinamicamente o vetor do disco e calcula matematicamente o espaço alocado e a **fragmentação interna** (`block_size - used_bytes`) no último bloco de cada arquivo.

### Etapa 2: Subsistema de E/S, Escalonamento SSTF e RAID 5
* **Integração com E/S:** Cada bloco físico possui um mapeamento de cilindro/trilha (`track`). Operações de escrita alimentam a fila de requisições `io_queue`.
* **Escalonamento SSTF (*Shortest Seek Time First*):** Ordena iterativamente o atendimento das requisições pendentes buscando a trilha com a menor distância absoluta em relação à posição atual da cabeça de leitura (`min(unvisited, key=lambda x: abs(x - curr))`), calculando o deslocamento exato.
* **Tolerância a Falhas via RAID 5 Real (`write_raid5`):** 
  * Divide os dados em 2 blocos físicos de 4 KB (`Disco 1` e `Disco 2`).
  * Calcula matematicamente o bloco de paridade no `Disco 3` aplicando a operação lógica `XOR` byte a byte: `bytes(b1 ^ b2 for b1, b2 in zip(part1, part2))`.
  * Na simulação de falha, o `Disco 2` tem seus bytes fisicamente zerados na memória (`bytearray(4096)`).
  * A recuperação reconstrói cada byte do `Disco 2` realizando a operação `XOR` entre o `Disco 1` e a paridade do `Disco 3` (`b1 ^ bp`), validando se os bytes reconstruídos são idênticos aos originais (`recovered == part2`).

### Etapa 3: Segurança, ACL, Criptografia e Antivírus
* **Modos de Execução e Autenticação:** Diferenciação ativa entre `MODO_KERNEL` (`root`) e `MODO_USUARIO` (`carlos`). As senhas são armazenadas exclusivamente como hashes `SHA-256` combinados com *Salt* (`_hash_pw`).
* **Controle de Acesso (Matriz / ACL):** Cada arquivo e diretório possui proprietário, grupo e máscara octal de permissões (ex.: `750` -> `rwxr-x---`). O método `_check_acl()` valida bit a bit (`4=r`, `2=w`, `1=x`) antes de permitir leituras, escritas ou remoções.
* **Criptografia de Dados em Repouso (`encrypt_file`):** Deriva uma chave de 256 bits via `SHA-256` a partir da senha informada e aplica uma cifra `XOR` diretamente sobre os bytes gravados nos blocos físicos do arquivo, substituindo o texto em claro pelo *ciphertext* real no disco.
* **Antivírus e Varredura de Integridade (`antivirus_scan`):** A cada gravação legítima, o bloco registra o hash `SHA-256` oficial de seus bytes (`saved_hash`). A rotina de varredura percorre a árvore de arquivos, recalcula o hash `SHA-256` atual diretamente sobre a memória física de cada bloco (`calc_hash()`) e acusa alerta de violação caso algum bloco tenha sofrido adulteração direta no disco.

---

## Como Executar

1. Certifique-se de ter o **Python 3.6+** instalado.
2. Clone este repositório:
   ```bash
   git clone [https://github.com/AldoFerreira17/Aldo_Ferreira_SO.git](https://github.com/AldoFerreira17/Aldo_Ferreira_SO.git)
   cd Aldo_Ferreira_SO