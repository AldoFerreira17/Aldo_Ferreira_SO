# Simulador de Sistema de Arquivos

**Autor:** Aldo Ferreira
**Instituição:** Universidade Federal Rural de Pernambuco (UFRPE)
**Disciplina:** Sistemas Operacionais

Este projeto implementa um Simulador de Sistema de Arquivos em Python, atendendo aos requisitos de sistemas operacionais para manipulação de arquivos, diretórios e gerenciamento de blocos de disco.

## Funcionalidades

- **Hierarquia em Árvore:** Estrutura navegável de diretórios e arquivos.
- **Operações:** Criação de diretórios (`mkdir`) e arquivos (`create`).
- **Alocação Física:** Simulação de alocação indexada (i-node) em blocos de tamanho fixo (4 KB).
- **Diagnóstico do Disco:** 
  - Mapa de ocupação de blocos por arquivo.
  - Cálculo de fragmentação interna (desperdício de espaço no último bloco).
  - Indicação de fragmentação externa e necessidade de compactação.
