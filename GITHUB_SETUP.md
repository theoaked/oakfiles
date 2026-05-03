# Configuração de Pipeline CI/CD e Proteção de Branch

## 📋 O que foi configurado

### 1. Pipeline GitHub Actions (CI)
O workflow `.github/workflows/ci.yml` executa automaticamente:
- **Testes unitários** com pytest (Python 3.9, 3.10, 3.11)
- **Cobertura de testes** com pytest-cov
- **Lint de código** com flake8
- **Upload de relatórios** para Codecov

### 2. Estrutura de Testes
```
tests/
├── __init__.py
├── conftest.py        # Configuração do pytest
└── test_basic.py      # Testes básicos da aplicação
```

Arquivo de configuração: `pytest.ini`

---

## 🚀 Como usar

### Executar testes localmente
```bash
# Instalar dependências (incluindo pytest)
pip install -r requirements.txt

# Executar todos os testes
pytest

# Executar com cobertura
pytest --cov=app --cov-report=html

# Executar com output verboso
pytest -v
```

### Adicionar novos testes
Crie arquivos com prefixo `test_` na pasta `tests/`:
```python
# tests/test_my_feature.py
def test_something():
    assert True
```

---

## 🔐 Configurar Proteção de Branch no GitHub

### Passos para bloquear commits diretos na `main` e forçar passar por `develop`:

#### 1. **Para a branch `main`**

1. Vá para o repositório no GitHub
2. Clique em **Settings** (Configurações)
3. No menu lateral, clique em **Branches**
4. Clique em **Add rule** (Adicionar regra)
5. Preencha os campos:
   - **Branch name pattern**: `main`
   - Marque as seguintes opções:
     - ✅ **Require a pull request before merging**
       - ✅ Require approvals (require at least 1)
     - ✅ **Require status checks to pass before merging**
       - Selecione: `tests` e `lint` (workflows do GitHub Actions)
     - ✅ **Require branches to be up to date before merging**
     - ✅ **Restrict who can push to matching branches**
       - (Opcional) Apenas certos usuários/teams
     - ✅ **Allow force pushes** → Desmarcar (não permitir)
     - ✅ **Allow deletions** → Desmarcar (não permitir)
6. Clique em **Create**

#### 2. **Para a branch `develop`**

1. Volte para **Settings > Branches**
2. Clique em **Add rule**
3. Preencha os campos:
   - **Branch name pattern**: `develop`
   - Marque as seguintes opções:
     - ✅ **Require a pull request before merging**
       - ✅ Require approvals (require at least 1)
     - ✅ **Require status checks to pass before merging**
       - Selecione: `tests` e `lint`
     - ✅ **Require branches to be up to date before merging**
     - ✅ **Allow force pushes** → Desmarcar
     - ✅ **Allow deletions** → Desmarcar
4. Clique em **Create**

---

## 📊 Fluxo de Trabalho Recomendado

```
1. Criar feature branch a partir de develop
   $ git checkout -b feature/nova-feature develop

2. Fazer commits e push
   $ git push origin feature/nova-feature

3. Criar Pull Request (PR) para develop
   - GitHub Actions executa testes e lint automaticamente
   - Se todos os testes passarem ✅, pode fazer merge

4. Quando pronto para produção, criar PR de develop para main
   - GitHub Actions executa testes novamente
   - Requer aprovação antes de fazer merge
   - Faz merge em main

5. Deploy em produção
```

---

## 🔍 Monitorar a Pipeline

### No GitHub
- Abra a aba **Actions** para ver o status dos workflows
- Cada PR mostrará se os testes passaram ou falharam
- Clique na verificação com ❌ para ver os detalhes do erro

### Localmente
```bash
# Ver status de uma branch específica
git status

# Ver logs de commits
git log --oneline

# Verificar diferenças antes de push
git diff
```

---

## 💡 Dicas

1. **Ninguém consegue fazer push direto em `main` ou `develop`**
   - Sempre use Feature Branches
   - Abra um Pull Request para qualquer mudança

2. **Os testes devem passar antes de fazer merge**
   - Se um teste falhar, corrija o código na sua branch
   - Push novamente e o workflow roda automaticamente

3. **Para adicionar mais testes**
   - Crie novos arquivos em `tests/` com prefixo `test_`
   - Os testes descobertos automaticamente pelo pytest
   - Rodas localmente com `pytest` antes de fazer push

4. **Para ignorar certas pastas nos testes**
   - Modifique `pytest.ini` se necessário

---

## 📝 Estrutura de Branches Recomendada

```
main
  ↑
  └── (Pull Request com aprovação e testes passando)
       
develop
  ↑
  ├── feature/user-auth
  ├── feature/api-endpoints
  ├── bugfix/login-issue
  └── ...

(Feature branches saem de develop e retornam via PR)
```

---

## ⚠️ Importante

- A proteção de branch é **obrigatória** no GitHub
- Commits diretos em `main` e `develop` serão **bloqueados**
- PRs só podem ser mergeadas se:
  - ✅ Todos os testes passarem
  - ✅ Lint passar
  - ✅ Houver aprovação (se configurado)
  - ✅ Branch estiver atualizada com main/develop

---

## 🆘 Troubleshooting

### Problema: "This branch has no status checks"
**Solução**: O workflow ainda não rodou. Abra uma PR para disparar o workflow.

### Problema: Teste falhando no GitHub Actions mas passando localmente
**Solução**: Pode haver diferença de ambiente (Python version, dependências, etc)
- Verifique a versão do Python local
- Execute `pip install -r requirements.txt` novamente

### Problema: Não consigo fazer push
**Solução**: Você pode estar tentando fazer push direto em `main`/`develop`
- Crie um feature branch: `git checkout -b feature/seu-nome`
- Faça push do feature branch
- Abra um PR

