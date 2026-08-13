import os
import shutil
import json
from models import parse_metadata_inteligente, extrair_diagnostico_inteligente, agrupar_componentes_inteligente

def main():
    base_dir = "base de conhecimento"
    output_dir = os.path.join("tests", "golden")

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    todos_arquivos = []
    for root, _, files in os.walk(base_dir):
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, base_dir)
            todos_arquivos.append((full_path, rel_path, f))

    todos_arquivos.sort(key=lambda x: x[1].replace('\\', '/'))

    total_processados = 0
    total_erros = 0
    lista_erros = []
    lista_degradados = []

    for caminho, rel_path, nome in todos_arquivos:
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

            if meta.get("status") == "UNKNOWN":
                lista_degradados.append(rel_path.replace('\\', '/'))

            golden_data = {
                "meta": meta,
                "diagnostico": diag,
                "componentes_agrupados": grupos
            }

            flat_name = rel_path.replace('\\', '/').replace('/', '__')
            out_json_path = os.path.join(output_dir, f"{flat_name}.json")
            with open(out_json_path, 'w', encoding='utf-8') as out_f:
                json.dump(golden_data, out_f, ensure_ascii=False, indent=2, sort_keys=True)

            total_processados += 1

        except Exception as e:
            total_erros += 1
            lista_erros.append(f"{rel_path}: {e}")

    print(f"Total processados: {total_processados}")
    print(f"Total com erro: {total_erros}")
    if lista_erros:
        print("Lista de erros:")
        for err in lista_erros:
            print(f"  - {err}")
    else:
        print("Lista de erros: []")

    print(f"Total parse degradado: {len(lista_degradados)}")
    if lista_degradados:
        print("Parse degradado:")
        for item in lista_degradados:
            print(f"  - {item}")
    else:
        print("Parse degradado: []")

if __name__ == "__main__":
    main()
