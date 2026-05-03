"""Testes básicos da aplicação."""

import sys
from pathlib import Path

# Adicionar raiz ao path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))


def test_imports():
    """Verifica se os módulos principais podem ser importados."""
    try:
        from app import config
        from app import database
        from app import mdns
        from app import models
        assert True
    except ImportError as e:
        assert False, f"Erro ao importar módulo: {e}"


def test_app_structure():
    """Verifica se a estrutura da aplicação existe."""
    from pathlib import Path
    
    app_dir = Path(__file__).parent.parent / "app"
    assert app_dir.exists(), "Diretório 'app' não encontrado"
    
    required_files = [
        "config.py",
        "database.py",
        "mdns.py",
        "models.py",
    ]
    
    for file in required_files:
        file_path = app_dir / file
        assert file_path.exists(), f"Arquivo esperado não encontrado: {file}"


def test_main_exists():
    """Verifica se o arquivo main.py existe."""
    from pathlib import Path
    
    main_file = Path(__file__).parent.parent / "main.py"
    assert main_file.exists(), "Arquivo main.py não encontrado"
