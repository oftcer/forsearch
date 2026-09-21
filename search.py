import os
import time
from tqdm import tqdm
import urllib.parse

def buscar_e_escrever_linhas_com_palavra_chave(nome_arquivo, palavra_chave):
    """Busca linhas que contêm a palavra-chave em um arquivo."""
    linhas_relevantes = []
    erros_decodificacao = 0
    try:
        with open(nome_arquivo, 'rb') as arquivo:
            for linha_bytes in arquivo:
                try:
                    linha = linha_bytes.decode('utf-8')
                    if palavra_chave in linha:
                        linhas_relevantes.append(linha.strip())
                except UnicodeDecodeError:
                    erros_decodificacao += 1
    except FileNotFoundError:
        print(f"Arquivo não encontrado: {nome_arquivo}")
    return linhas_relevantes, erros_decodificacao

def limpar_nome_arquivo(nome_arquivo):
    """Remove caracteres inválidos do nome do arquivo."""
    caracteres_invalidos = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in caracteres_invalidos:
        nome_arquivo = nome_arquivo.replace(char, '_')
    return nome_arquivo

def main():
    """Função principal do script."""
    pasta_db = "comeputa"

    # Verifica se o diretório existe
    if not os.path.isdir(pasta_db):
        print(f"Diretório '{pasta_db}' não encontrado. Certifique-se de que ele existe.")
        return

    palavra_chave = input("Qual URL deseja buscar legitz?: ")
    palavra_chave_encoded = urllib.parse.quote(palavra_chave)

    nome_arquivo_saida = f"{limpar_nome_arquivo(palavra_chave_encoded)}.txt"

    # Lista os arquivos .txt na pasta
    arquivos_txt = [arquivo for arquivo in os.listdir(pasta_db) if arquivo.endswith('.txt')]

    if not arquivos_txt:
        print(f"Nenhum arquivo .txt encontrado no diretório '{pasta_db}'.")
        return

    total_linhas_encontradas = 0
    total_erros_decodificacao = 0

    with open(nome_arquivo_saida, 'w', encoding='utf-8') as arquivo_saida:
        with tqdm(total=len(arquivos_txt), desc="Progresso da pesquisa") as progresso_barra:
            for arquivo_txt in arquivos_txt:
                caminho_arquivo = os.path.join(pasta_db, arquivo_txt)
                linhas_relevantes, erros_decodificacao = buscar_e_escrever_linhas_com_palavra_chave(caminho_arquivo, palavra_chave)
                total_linhas_encontradas += len(linhas_relevantes)
                total_erros_decodificacao += erros_decodificacao

                if linhas_relevantes:
                    arquivo_saida.write(f"Linhas relevantes de '{arquivo_txt}':\n")
                    arquivo_saida.writelines("\n".join(linhas_relevantes))
                    arquivo_saida.write("\n\n")

                progresso_barra.update(1)
                time.sleep(0.1)

    if total_linhas_encontradas == 0:
        print("Nenhuma linha relevante encontrada.")
    else:
        print(f"Processo concluído. {total_linhas_encontradas} linhas relevantes foram encontradas e escritas no arquivo '{nome_arquivo_saida}'.")

    if total_erros_decodificacao > 0:
        print(f"Total de erros de decodificação: {total_erros_decodificacao}")

if __name__ == "__main__":
    main()
