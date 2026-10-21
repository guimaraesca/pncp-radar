import os
import time

def cleanup_old_files(base_dir, retention_days=14):
    """
    Remove arquivos de editais (PDFs e TXTs) com mais de retention_days dias de criacao/modificacao.
    Mantem o repositorio do GitHub leve e organizado dentro da politica de retencao.
    """
    editais_dir = os.path.join(base_dir, "data", "editais")
    if not os.path.exists(editais_dir):
        return 0
        
    cutoff_time = time.time() - (retention_days * 86400)
    purged_count = 0
    
    for root, dirs, files in os.walk(editais_dir, topdown=False):
        for f in files:
            file_path = os.path.join(root, f)
            try:
                if os.path.getmtime(file_path) < cutoff_time:
                    os.remove(file_path)
                    purged_count += 1
            except Exception as e:
                print(f"Erro ao remover arquivo antigo {file_path}: {e}")
                
        # Remove pastas vazias
        if root != editais_dir and not os.listdir(root):
            try:
                os.rmdir(root)
            except Exception:
                pass
                
    if purged_count > 0:
        print(f"Politica de Retencao (14 dias): {purged_count} arquivos antigos foram removidos do armazenamento.")
    return purged_count

def ensure_storage_dirs(base_dir, sources):
    """
    Garante a criacao da estrutura de diretorios em data/editais/<fonte>/
    """
    for src in sources:
        dir_path = os.path.join(base_dir, src.get('dir', f"data/editais/{src['id']}"))
        os.makedirs(dir_path, exist_ok=True)
