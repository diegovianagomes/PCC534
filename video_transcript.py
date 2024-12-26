import os
from datetime import datetime, timedelta
import pandas as pd
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from supabase import create_client, Client
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# Biblioteca para detectar idioma
from langdetect import detect, LangDetectException


def load_config():
    """
    Carrega as variáveis de ambiente do arquivo .env
    """
    load_dotenv()
    return {
        "youtube_api_key": os.getenv("YOUTUBE_API_KEY"),
        "gemini_key": os.getenv("GEMINI_API_KEY"),
        "supabase_url": os.getenv("SUPABASE_URL"),
        "supabase_key": os.getenv("SUPABASE_KEY"),
    }


def setup_supabase(url, key):
    """
    Configura e retorna o cliente Supabase.
    """
    return create_client(url, key)


def get_YT(api_key: str):
    """
    Retorna uma instância do serviço da YouTube Data API.
    """
    return build("youtube", "v3", developerKey=api_key)


def search_videos(youtube, query: str, days: int = 7, max_results: int = 50):
    """
    Busca vídeos no YouTube baseados em um termo (query), com paginação.
    - days: quantidade de dias para filtrar vídeos recentes.
    - max_results: limite máximo de vídeos a serem retornados.
    """
    date_video = (datetime.now() - timedelta(days=days)).isoformat("T") + "Z"
    results = []
    total_results = 0
    next_page_token = None

    while total_results < max_results:
        response = (
            youtube.search()
            .list(
                q=query,
                part="snippet",
                maxResults=min(50, max_results - total_results),
                type="video",
                publishedAfter=date_video,
                videoDuration="long",
                videoDefinition="high",
                order="relevance",
                pageToken=next_page_token
            )
            .execute()
        )

        for item in response.get("items", []):
            if video_id := item.get("id", {}).get("videoId"):
                # Obter alguns detalhes do vídeo
                video_response = (
                    youtube.videos()
                    .list(part="snippet,statistics,contentDetails", id=video_id)
                    .execute()
                )

                if video_response["items"]:
                    snippet = video_response["items"][0]["snippet"]
                    results.append(
                        {
                            "Title": snippet["title"],
                            "Description": snippet.get("description", "No Description"),
                            "channel": snippet["channelTitle"],
                            "Link": f"https://www.youtube.com/watch?v={video_id}",
                        }
                    )

        total_results += len(response.get("items", []))
        next_page_token = response.get("nextPageToken")

        if not next_page_token:
            break

    return results


def extract_videoId(link: str):
    """
    Extrai o videoId do link do YouTube.
    Exemplo de link: 'https://www.youtube.com/watch?v=abcdef12345'
    """
    return link.split("v=")[-1]


def fetch_transcript(video_id: str, languages=["en", "pt", "pt-BR"]) -> str:
    """
    Tenta buscar a transcrição do vídeo no YouTube, detecta o idioma e,
    caso não seja 'en' ou 'pt', retorna None (para gravar NULL no banco).
    """
    try:
        # Tenta obter a transcrição (pode tentar 'en', 'pt', 'pt-BR', etc.)
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        # Concatena todos os pedaços de texto das legendas em uma única string
        transcript_text = " ".join([item["text"] for item in transcript_list])

        # Detecta o idioma
        if transcript_text.strip():
            try:
                lang = detect(transcript_text)
                if lang not in ["en", "pt"]:
                    print(f"Transcrição para vídeo {video_id} detectada como '{lang}', configurando None.")
                    transcript_text = None
            except LangDetectException:
                # Se não for possível detectar, também definimos como None
                transcript_text = None

        return transcript_text

    except (TranscriptsDisabled, NoTranscriptFound) as e:
        print(f"Transcrição indisponível para o vídeo {video_id}: {e}")
        return None
    except Exception as e:
        print(f"Erro ao buscar transcrição para o vídeo {video_id}: {e}")
        return None


def already_transcripted(supabase, video_id: str) -> bool:
    """
    Verifica se o video_id já possui transcrição na tabela 'transcriptions'.
    """
    response = supabase.table("transcriptions").select("id").eq("video_id", video_id).execute()
    return len(response.data) > 0


def save_transcription(supabase: Client, video_id: str, transcript_text: str):
    """
    Salva a transcrição do vídeo na tabela 'transcriptions'.
    Se transcript_text for None, o banco grava como NULL.
    """
    data = {
        "video_id": video_id,
        "transcript_text": transcript_text
    }
    try:
        response = supabase.table("transcriptions").insert(data).execute()
        if not response.data:
            print(f"Erro ao salvar transcrição do vídeo {video_id}. Resposta: {response}")
        else:
            if transcript_text is None:
                print(f"Transcrição do vídeo {video_id} armazenada como NULL (idioma != en/pt).")
            else:
                print(f"Transcrição do vídeo {video_id} salva com sucesso!")
    except Exception as e:
        print(f"Exceção ao tentar salvar transcrição do vídeo {video_id}: {e}")


def evaluate_video(title: str, description: str, channel: str, gemini_key: str):
    """
    Envia uma requisição à API (modelo Gemini) para análise qualitativa do vídeo.
    Ajuste o prompt conforme necessário.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
    headers = {"Content-Type": "application/json"}

    text_content = (
        f"Title: {title}\nDescription: {description}\nChannel: {channel}\n"
        "Avalie a qualidade do vídeo e a metodologia de ensino, focando na didática utilizada "
        "para apresentar e explicar algoritmos e estruturas de dados. O conteúdo foi claro "
        "e envolvente ou causou confusão? Dê uma avaliação detalhada, considerando a implementação "
        "e aprendizado dos tópicos a seguir:\n"
        "1. Arrays\n"
        "2. Linked Lists\n"
        "3. Stacks\n"
        "4. Trees\n"
        "5. Graphs\n"
        "6. Asymptotic Analysis\n"
        "Para cada tópico, verifique se foi abordado no vídeo, como foi implementado e o quão "
        "efetiva foi a explicação. Aponte pontos fortes e pontos que podem ser melhorados."
    )

    payload = {
        "prompt": {
            "text": text_content
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            analysis = response.json()
            # Ajuste a extração do texto de acordo com o formato retornado pela API
            content = analysis.get("candidates", [])
            if content and len(content) > 0:
                # Exemplo de extração, pois o formato pode variar
                parts = content[0].get("content", {}).get("parts", [])
                if parts and len(parts) > 0:
                    return parts[0].get("text", "Sem texto de avaliação.")
                # Se o formato for diferente, adapte aqui.
            return "Não foi possível extrair a análise de Gemini."
        else:
            return f"Erro na requisição: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Exceção ao requisitar avaliação Gemini: {e}"


def evaluate_videos(videos, gemini_key):
    """
    Faz a avaliação (via Gemini) para cada vídeo e retorna a lista de vídeos com o campo 'Qualitative analysis'.
    """
    for video in videos:
        video_id = extract_videoId(video["Link"])
        print(f"Avaliando vídeo: {video_id} - {video['Title']}")
        analysis = evaluate_video(
            title=video["Title"],
            description=video["Description"],
            channel=video["channel"],
            gemini_key=gemini_key,
        )
        video["Qualitative analysis"] = analysis
    return videos


def file_in_use(file_name):
    """
    Verifica se um arquivo está em uso,
    tentando abri-lo em modo append.
    Se não der erro, não está em uso.
    """
    try:
        with open(file_name, "a"):
            return False
    except IOError:
        return True


def save_excel(data, file_name: str = "youtube_videos_evaluated.xlsx"):
    """
    Salva dados em um arquivo Excel.
    """
    if file_in_use(file_name):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"youtube_videos_evaluated_{timestamp}.xlsx"
        print(f"Arquivo estava aberto. Salvando como: {file_name}")

    df = pd.DataFrame(data)
    df.to_excel(file_name, index=False)
    print(f"Dados salvos no arquivo: {file_name}")


def already_saved(supabase, video_id: str):
    """
    Verifica se um vídeo já está no banco, procurando pelo link correspondente na tabela 'videos'.
    """
    response = supabase.table("videos").select("id").eq("link", f"https://www.youtube.com/watch?v={video_id}").execute()
    return len(response.data) > 0


def save_database(data, supabase):
    """
    Salva dados dos vídeos na tabela 'videos'.
    """
    for item in data:
        video_id = extract_videoId(item["Link"])

        # Verifica se já existe
        if already_saved(supabase, video_id):
            print(f"Vídeo '{item['Title']}' já existe no banco. Pulando...")
            continue

        # Insere
        row = {
            "title": item["Title"],
            "description": item["Description"],
            "channel": item["channel"],
            "link": item["Link"],
            "qualitative_analysis": item.get("Qualitative analysis", "")
        }

        try:
            response = supabase.table("videos").insert(row).execute()
            if not response.data:
                print(f"Erro ao inserir vídeo '{item['Title']}': {response}")
            else:
                print(f"Vídeo '{item['Title']}' inserido com sucesso!")
        except Exception as e:
            print(f"Exceção ao inserir vídeo '{item['Title']}': {e}")


def main():
    # Carrega configurações
    config = load_config()
    supabase = setup_supabase(config["supabase_url"], config["supabase_key"])
    youtube_service = get_YT(config["youtube_api_key"])

    # Define a query (ajuste conforme sua necessidade)
    query = "Algorithm+Advent of Code+Python+2024"

    # 1) Buscar vídeos
    videos = search_videos(youtube_service, query, days=7, max_results=50)

    # 2) Para cada vídeo, buscar transcrição e salvar no banco (NULL se idioma != en/pt)
    for video in videos:
        video_id = extract_videoId(video["Link"])
        
        if already_transcripted(supabase, video_id):
            print(f"Transcrição para o vídeo '{video_id}' já existe. Pulando...")
        else:
            # fetch_transcript retorna None se não for en/pt
            transcript_text = fetch_transcript(video_id, languages=["en", "pt", "pt-BR"])
            save_transcription(supabase, video_id, transcript_text)

    # 3) Avaliar vídeos com Gemini
    videos_with_analysis = evaluate_videos(videos, config["gemini_key"])

    # 4) Salvar em Excel
    save_excel(videos_with_analysis)

    # 5) Salvar no banco de dados (tabela 'videos')
    save_database(videos_with_analysis, supabase)


if __name__ == "__main__":
    main()
