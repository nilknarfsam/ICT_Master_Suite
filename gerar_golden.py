import os
import json
from datetime import datetime
from models import parse_metadata_inteligente, extrair_diagnostico_inteligente, agrupar_componentes_inteligente

def main():
    base_dir = "base de conhecimento"
    output_dir = os.path.join("tests", "golden")
    os.makedirs(output_dir, exist_ok=True)

    # Coleta todos os arquivos de forma ordenada e determinística
    todos_arquivos = []
    for root, _, files in os.walk(base_dir):
        for f in files:
            full_path = os.path.join(root, f)
            todos_arquivos.append((full_path, f))

    todos_arquivos.sort(key=lambda x: x[0].replace('\\', '/'))

    total_processados = 0
    total_erros = 0
    lista_erros = []

    for caminho, nome in todos_arquivos:
        try:
            with open(caminho, 'r', encoding='utf-8', errors='ignore') as file_obj:
                conteudo = file_obj.read()

            meta = parse_metadata_inteligente(caminho, nome, conteudo)
            diag = extrair_diagnostico_inteligente(meta, conteudo)
            grupos = agrupar_componentes_inteligente(diag.get("componentes", []))

            # Substitui data por <MTIME> caso a origem da data seja os.path.getmtime()
            nome_sem_ext = os.path.splitext(nome)[0]
            is_tri_csv_with_ts = (
                meta.get("tipo") == "TRI" 
                and nome.lower().endswith(".csv") 
                and nome_sem_ext[:14].isdigit()
            )
            if not is_tri_csv_with_ts and meta.get("data") != "N/A":
                meta["data"] = "<MTIME>"

            golden_data = {
                "meta": meta,
                "diagnostico": diag,
                "componentes_agrupados": grupos
            }

            out_json_path = os.path.join(output_dir, f"{nome}.json")
            with open(out_json_path, 'w', encoding='utf-8') as out_f:
                json.dump(golden_data, out_f, ensure_ascii=False, indent=2, sort_keys=True)

            total_processados += 1

        except Exception as e:
            total_erros += 1
            lista_erros.append(f"{caminho}: {e}")

    print(f"Total processados: {total_processados}")
    print(f"Total com erro: {total_erros}")
    if lista_erros:
        print("Erros:")
        for err in lista_erros:
            print(f"  - {err}")
    else:
        print("Lista de erros: []")

if __name__ == "__main__":
    main()
