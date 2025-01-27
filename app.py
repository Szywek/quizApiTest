from flask import Flask, render_template, jsonify, request
import random
import requests
import os
app = Flask(__name__)

# URL API
API_URL = "https://anisongdb.com/api/annId_request"
AUDIO_BASE_URL = "https://naedist.animemusicquiz.com/"

# Funkcja generująca listę sezonów w zadanym zakresie
def generate_season_range(start_season, start_year, end_season, end_year):
    seasons = ["Winter", "Spring", "Summer", "Fall"]
    season_years = []
    # Rozpocznij od konkretnego start_season i start_year
    current_year = start_year
    current_season_index = seasons.index(start_season)
    while current_year < end_year or (current_year == end_year and current_season_index <= seasons.index(end_season)):
        # Dodaj aktualny sezon i rok do listy
        season_years.append(f"{seasons[current_season_index]} {current_year}")

        # Przejdź do następnego sezonu
        current_season_index += 1
        if current_season_index >= len(seasons):
            # Przejdziesz na kolejny rok po "Fall"
            current_season_index = 0
            current_year += 1

    return season_years

# Funkcja ładująca wszystkie annId z odpowiednich plików w katalogu `dates`
def load_ids_from_season_files(seasons, folder="dates"):
    all_ids = []
    for season in seasons:
        file_path = os.path.join(folder, f"{season}.txt")
        try:
            with open(file_path, 'r') as file:
                # Wczytaj wszystkie identyfikatory z pliku
                ids = [int(line.strip()) for line in file if line.strip().isdigit()]
                all_ids.extend(ids)
        except FileNotFoundError:
            print(f"WARNING: Plik dla sezonu '{season}' ({file_path}) nie został znaleziony.")
        except Exception as e:
            print(f"ERROR: Wystąpił problem podczas odczytu pliku {file_path}: {e}")
    return all_ids

# Funkcja do wczytywania identyfikatorów z pliku
def load_ids_from_file(file_path):
    try:
        with open(file_path, 'r') as file:
            # Wczytaj wszystkie linie, usuń białe znaki i upewnij się, że są liczbami
            ids = [int(line.strip()) for line in file if line.strip().isdigit()]
        return ids
    except FileNotFoundError:
        print(f"ERROR: Plik {file_path} nie został znaleziony.")
        return []
    except Exception as e:
        print(f"ERROR: Wystąpił błąd podczas wczytywania pliku {file_path}: {e}")
        return []

def filter_vintage(vintage, start_season, start_year, end_season, end_year):
    """
    Filtruje `animeVintage` względem zakresu sezonów/lat.
    - Odrzuca utwór, jeśli `animeVintage` jest starsze niż startowy sezon i rok.
    - Odrzuca utwór, jeśli `animeVintage` jest nowsze niż końcowy sezon i rok.
    """
    try:
        # Mapowanie sezonów na wartości porządkowe
        seasons = {"Winter": 1, "Spring": 2, "Summer": 3, "Fall": 4}

        # Rozbicie vintage na sezon i rok
        season, year = vintage.split()
        year = int(year)

        # Sprawdzanie, czy `vintage` jest starszy niż początek zakresu
        if year < start_year:  # Rok jest za stary
            print(f"DEBUG: {vintage} jest starszy niż {start_season} {start_year}")
            return False

        if year == start_year and seasons[season] < seasons[start_season]:  # Sezon jest za stary
            print(f"DEBUG: {vintage} jest starszy niż {start_season} {start_year}")
            return False

        # Sprawdzanie, czy `vintage` jest nowszy niż koniec zakresu
        if year > end_year:  # Rok jest za nowy
            print(f"DEBUG: {vintage} jest nowszy niż {end_season} {end_year}")
            return False

        if year == end_year and seasons[season] > seasons[end_season]:  # Sezon jest za nowy
            print(f"DEBUG: {vintage} jest nowszy niż {end_season} {end_year}")
            return False

        # Jeśli rok i sezon są w granicach, zaakceptuj
        print(f"DEBUG: {vintage} mieści się w zakresie.")
        return True

    except Exception as e:
        # Obsługa ewentualnych błędów
        print(f"ERROR: Problem z parsowaniem animeVintage: {vintage} ({e})")
        return False


# Pobieranie danych o utworze z API na podstawie annId
def get_song_data(annId):
    payload = {
        "annId": annId,
        "ignore_duplicate": False,
        "opening_filter": True,
        "ending_filter": True,
        "insert_filter": False
    }
    response = requests.post(API_URL, json=payload)
    if response.status_code == 200:
        data = response.json()
        print(f"DEBUG: Odpowiedź API dla annId={annId}: {data}")
        return data
    else:
        print(f"DEBUG: Błąd podczas pobierania danych dla annId={annId}: {response.status_code} {response.text}")
    return None


# Widok główny
@app.route('/')
def index():
    return render_template('index.html')


# Endpoint do losowania utworów
@app.route('/play', methods=['GET'])
def play_song():
    playback_start_percentage = int(request.args.get('playback_start_percentage', 50))  # Domyślne 50%
    song_types = request.args.get('song_types', '').split(',')  # Typy utworów (np. Opening, Ending)
    remaining_ids = []  # Globalna lista dostępnych identyfikatorów
    start_season = request.args.get('start_season', 'Winter')  # Początkowy sezon
    start_year = int(request.args.get('start_year', 1990))  # Początkowy rok
    end_season = request.args.get('end_season', 'Winter')  # Końcowy sezon
    end_year = int(request.args.get('end_year', 2030))  # Końcowy rok

    # Jeśli lista jest pusta, ładujemy identyfikatory na nowo
    if not remaining_ids:
        seasons_in_range = generate_season_range(start_season, start_year, end_season, end_year)
        remaining_ids.extend(load_ids_from_season_files(seasons_in_range))
    if not remaining_ids:
        return jsonify({"error": "Nie znaleziono żadnych utworów w podanym zakresie"}), 404

    while remaining_ids:  # Pętla losująca, aż znajdziemy odpowiedni utwór
        annId = random.choice(remaining_ids)  # Wylosuj identyfikator z dostępnych
        song_data = get_song_data(annId)

        # Usuń wylosowany identyfikator z listy
        remaining_ids.remove(annId)

        if not song_data or len(song_data) == 0:
            continue  # Próbuj dalej, jeśli brak wyników


        # Filtrujemy utwory na podstawie zaznaczonych typów (np. Opening/Ending)
        filtered_songs = [
            song for song in song_data
            if 'songType' in song and any(song['songType'].startswith(st) for st in song_types)
        ]

        if not filtered_songs:  # Brak wyników po filtrowaniu
            continue

        # Losowanie utworu z przefiltrowanej listy
        selected_song = random.choice(filtered_songs)

        # Przygotowanie adresu URL audio w preferowanej kolejności
        audio_url = selected_song.get('audio')
        hq_url = selected_song.get('HQ')
        mq_url = selected_song.get('MQ')
        song_url = None

        if audio_url:
            song_url = f"{AUDIO_BASE_URL}{audio_url}"
        elif hq_url and (hq_url.endswith('.webm') or hq_url.endswith('.mp4')):
            song_url = f"{AUDIO_BASE_URL}{hq_url}"
        elif mq_url and (mq_url.endswith('.webm') or mq_url.endswith('.mp4')):
            song_url = f"{AUDIO_BASE_URL}{mq_url}"
        else:
            print(f"ERROR: Brak dostępnych ścieżek audio dla annId={annId}")
            continue

        # Sprawdzamy długość utworu
        song_length = selected_song.get('songLength')
        if not isinstance(song_length, (int, float)):
            print(f"WARNING: Długość utworu dla annId={annId} ustawiona domyślnie na 95 sekund.")
            song_length = 95  # Domyślna długość

        # Obliczanie czasu startowego
        start_time = float(song_length * (playback_start_percentage / 100))

        # Przygotowujemy odpowiedź JSON
        song_info = {
            'songName': selected_song['songName'],
            'songArtist': selected_song['songArtist'],
            'songType': selected_song['songType'],
            'animeJPName': selected_song['animeJPName'],
            'animeVintage': selected_song.get('animeVintage', 'Nieznany sezon i rok'),
            'audioUrl': song_url,
            'songLength': song_length,
            'startTime': start_time,
            'roundCount': len(remaining_ids)  # Dodaj bieżący licznik utworów
        }

        # Jeśli oba typy są włączone, losowo wybierz jeden
        if len(song_types) == 2:  # Zarówno Opening, jak i Ending zaznaczone
            ending_songs = [song for song in song_data if song['songType'].startswith('Ending')]
            opening_songs = [song for song in song_data if song['songType'].startswith('Opening')]

            if ending_songs and opening_songs:
                # Losujemy albo Opening, albo Ending
                both_types = random.choice(['Opening', 'Ending'])

                if both_types == "Ending":
                    selected_song = random.choice(ending_songs)
                else:
                    selected_song = random.choice(opening_songs)

                # Aktualizacja JSON dla losowanego typu
                song_info = {
                    'songName': selected_song['songName'],
                    'songArtist': selected_song['songArtist'],
                    'songType': selected_song['songType'],
                    'animeJPName': selected_song['animeJPName'],
                    'animeVintage': selected_song.get('animeVintage', 'Nieznany sezon i rok'),
                    'audioUrl': song_url,
                    'songLength': song_length,
                    'startTime': start_time
                }

        return jsonify(song_info)  # Zwracamy wybrany utwór


if __name__ == '__main__':
    app.run(debug=True)
