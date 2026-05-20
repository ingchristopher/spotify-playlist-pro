import sys
import os
import re
import random
import subprocess
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

import spotipy
from spotipy.oauth2 import SpotifyPKCE

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWebEngineWidgets import *
from PyQt6.QtWebEngineCore import *


BASE_ENV = Path(__file__).parent.resolve()

import sys

possible_envs = [
    BASE_ENV / ".env",
    Path.cwd() / ".env",
    Path(getattr(sys, "_MEIPASS", BASE_ENV)) / ".env",
    Path(__file__).parent / ".env",
    Path.home() / "Documents" / "SpotifyPlaylistPro" / ".env",
]

for env_file in possible_envs:
    if env_file.exists():
        load_dotenv(env_file)
        break



BASE = Path(__file__).parent.resolve()

DATA_DIR = Path.home() / "Documents" / "SpotifyPlaylistPro"
DATA_DIR.mkdir(parents=True, exist_ok=True)


FILES = {
    "artists": DATA_DIR / "artist_links.txt",
    "ideas": DATA_DIR / "ideas_nombres.txt",
    "library": DATA_DIR / "biblioteca_artistas.txt",
    "generated": DATA_DIR / "playlist_generada_links.txt",
    "used": DATA_DIR / "canciones_usadas_historial.txt",
    "used_names": DATA_DIR / "nombres_usados.txt",
    "license": DATA_DIR / "license_local.txt",
    "created_playlists": DATA_DIR / "playlist_creadas.txt",
}

for f in FILES.values():
    f.touch(exist_ok=True)

SCOPES = "playlist-modify-public playlist-modify-private playlist-read-private"

def read(path):
    return [x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

def write(path, lines):
    path.write_text("\n".join(lines), encoding="utf-8")

def append(path, lines):
    old = read(path)
    with path.open("a", encoding="utf-8") as f:
        for line in lines:
            if line not in old:
                f.write(line + "\n")


def supabase_client():

    SUPABASE_URL_FIXED = "https://lahuiofwfypzplmekwou.supabase.co"
    SUPABASE_KEY_FIXED = "sb_publishable_3Anima4TCVgOhSqFCjjO_w_IPRJQYY6"

    url = os.getenv("SUPABASE_URL") or SUPABASE_URL_FIXED
    key = os.getenv("SUPABASE_KEY") or SUPABASE_KEY_FIXED

    return create_client(url, key)

def device_id():
    path = DATA_DIR / "device_id.txt"
    if path.exists():
        return path.read_text().strip()
    new_id = str(uuid.uuid4())
    path.write_text(new_id)
    return new_id


def get_app_config():
    db = supabase_client()
    result = db.table("app_config").select("*").eq("id", 1).execute()
    if not result.data:
        raise Exception("No existe app_config en Supabase")
    return result.data[0]

def sp():
    cfg = get_app_config()
    return spotipy.Spotify(auth_manager=SpotifyPKCE(
        client_id=cfg["spotify_client_id"],
        redirect_uri=cfg.get("spotify_redirect_uri", "http://127.0.0.1:8888/callback"),
        scope=SCOPES,
        cache_path=str(DATA_DIR / ".spotify_cache"),
        open_browser=True
    ))

def artist_id(link):
    m = re.search(r"artist/([A-Za-z0-9]+)", link)
    if m:
        return m.group(1)
    return link.strip()

class App(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Spotify Playlist Auto Pro")
        self.resize(1600, 950)

        self.setStyleSheet("""
            QWidget {
                background:#05080d;
                color:white;
                font-family:Arial;
            }

            QPushButton {
                background:#0066ff;
                color:white;
                font-size:18px;
                font-weight:900;
                border-radius:12px;
                padding:14px;
                border:2px solid white;
            }

            QPushButton:hover {
                background:#1DB954;
            }

            QTextEdit {
                background:#07111f;
                color:#00ff88;
                border:2px solid #1DB954;
                border-radius:8px;
                font-size:14px;
            }
        """)

        root = QHBoxLayout()

        left = QVBoxLayout()

        title = QLabel("Spotify Playlist Auto Pro")
        title.setStyleSheet("""
            font-size:26px;
            font-weight:bold;
            color:#1DB954;
        """)

        left.addWidget(title)

        credit = QLabel("Ing. Cedeno\nTelegram @ingcedeno")
        credit.setStyleSheet("font-size:13px;")
        left.addWidget(credit)

        self.usage_label = QLabel("Uso disponible: No activado")
        self.usage_label.setStyleSheet("""
            background:#ff0033;
            color:white;
            font-size:18px;
            font-weight:900;
            padding:10px;
            border-radius:10px;
            border:2px solid white;
        """)
        left.addWidget(self.usage_label)

        buttons = [
            ("🔐 Activar Licencia", self.activate_license),
            ("🎵 Generar Playlist", self.generate_playlist),
            ("🔁 Solo cambiar nombre", self.rename_only_free),
            ("👤 Mis Artistas", self.open_artists),
            ("➕ Agregar Artista", self.add_artist),
            ("📚 Playlists creadas", self.open_created_playlists),
            ("⚙️ Configuración", self.config),
        ]

        for text, fn in buttons:
            btn = QPushButton(text)
            btn.setMinimumHeight(60)
            btn.clicked.connect(fn)
            left.addWidget(btn)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setText("Consola lista...\n")
        left.addWidget(self.log)

        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setFixedWidth(380)

        self.profile = QWebEngineProfile("spotify_profile", self)

        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )

        self.profile.setPersistentStoragePath(
            str(BASE / "spotify_storage")
        )

        self.profile.setCachePath(
            str(BASE / "spotify_cache")
        )

        self.web = QWebEngineView()

        self.page = QWebEnginePage(self.profile, self.web)

        self.web.setPage(self.page)

        self.web.load(QUrl("https://open.spotify.com"))

        QTimer.singleShot(1500, self.update_usage_label)

        root.addWidget(left_widget)
        root.addWidget(self.web)

        self.setLayout(root)


    def update_usage_label(self):

        try:
            lic = self.get_license()

            if not lic:
                self.usage_label.setText("Uso disponible: No activado")
                return

            used = int(lic.get("used_playlists", 0))
            limit = int(lic.get("playlist_limit", 0))
            remaining = max(limit - used, 0)

            self.usage_label.setText(f"Uso disponible: {remaining} playlists")

        except Exception:
            self.usage_label.setText("Uso disponible: Error")

    def msg(self, text):
        self.log.append(str(text))
        QApplication.processEvents()




    def current_license_code(self):

        try:
            if FILES["license"].exists():
                code = FILES["license"].read_text(encoding="utf-8").strip()
                if code:
                    return code
        except Exception:
            pass

        return None

    def add_artist(self):

        code = self.current_license_code()

        if not code:
            self.msg("Primero activa una licencia para guardar tus artistas.")
            return

        artist, ok = QInputDialog.getText(
            self,
            "Agregar Artista",
            "Pega el link del artista de Spotify:"
        )

        if not ok or not artist.strip():
            return

        artist = artist.strip()

        if "open.spotify.com/artist/" not in artist and "spotify:artist:" not in artist:
            self.msg("Link inválido. Debe ser link de artista Spotify.")
            return

        try:
            db = supabase_client()

            db.table("user_artist_links").insert({
                "license_code": code,
                "artist_url": artist,
                "active": True
            }).execute()

            self.msg("Artista agregado a tu cuenta.")

        except Exception as e:

            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                self.msg("Ese artista ya existe en tu cuenta.")
            else:
                self.msg(str(e))


    def open_artists(self):

        code = self.current_license_code()

        if not code:
            self.msg("Primero activa licencia para ver tus artistas.")
            return

        try:
            db = supabase_client()

            result = db.table("user_artist_links").select("artist_url").eq("license_code", code).eq("active", True).execute()

            artists = [
                x["artist_url"]
                for x in result.data
                if x.get("artist_url")
            ]

            write(FILES["artists"], artists)

        except Exception as e:
            self.msg(str(e))

        import os, subprocess, platform
        path = str(FILES["artists"])

        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    def open_created_playlists(self):
        os.system(f"open '{FILES['created_playlists']}'")
        self.msg("Abriendo playlists creadas.")


    def config(self):
        import os, subprocess, platform
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.msg(f"Carpeta de datos:")
        self.msg(str(DATA_DIR))

        if platform.system() == "Windows":
            os.startfile(str(DATA_DIR))
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(DATA_DIR)])
        else:
            subprocess.run(["xdg-open", str(DATA_DIR)])


    def choose_name(self):

        try:
            db = supabase_client()
            result = db.table("playlist_names").select("name").eq("active", True).execute()
            names = [x["name"] for x in result.data if x.get("name")]

            if not names:
                return "Playlist Automática"

            used = set(read(FILES["used_names"]))
            available = [x for x in names if x not in used]

            if not available:
                write(FILES["used_names"], [])
                available = names

            name = random.choice(available)[:80]
            append(FILES["used_names"], [name])
            return name

        except Exception as e:
            self.msg(str(e))
            return "Playlist Automática"



    def update_library(self):

        client = sp()

        all_tracks = []

        code = self.current_license_code()

        if not code:
            self.msg("Primero activa una licencia.")
            return

        try:
            db = supabase_client()

            result = db.table("user_artist_links").select("artist_url").eq("license_code", code).eq("active", True).execute()

            artists = [
                x["artist_url"]
                for x in result.data
                if x.get("artist_url")
            ]

        except Exception as e:
            self.msg(str(e))
            artists = []

        if not artists:
            self.msg("No tienes artistas agregados. Presiona ➕ Agregar Artista.")
            write(FILES["library"], [])
            return

        for link in artists:

            aid = artist_id(link)

            self.msg(f"Leyendo artista: {aid}")

            try:

                artist_info = client.artist(aid)

                artist_name = artist_info.get("name", "")

                self.msg(f"Buscando canciones de: {artist_name}")

                for offset in range(0, 100, 10):

                    results = client.search(
                        q=f'artist:"{artist_name}"',
                        type="track",
                        limit=10,
                        offset=offset,
                        market="US"
                    )

                    items = results.get("tracks", {}).get("items", [])

                    if not items:
                        break

                    for t in items:

                        artist_names = [
                            a.get("name", "").lower()
                            for a in t.get("artists", [])
                        ]

                        if artist_name.lower() in artist_names and t.get("id"):

                            all_tracks.append(
                                f"https://open.spotify.com/track/{t['id']}"
                            )

                    time.sleep(0.25)

            except Exception as e:

                self.msg(str(e))

        unique = list(dict.fromkeys(all_tracks))

        write(FILES["library"], unique)

        self.msg(f"Biblioteca actualizada: {len(unique)} canciones")


    def get_open_playlist_id(self, callback):

        js = "window.location.href;"

        def got_url(current_url):

            self.msg(f"Playlist abierta: {current_url}")

            m = re.search(
                r"/playlist/([A-Za-z0-9]+)",
                current_url
            )

            if not m:
                self.msg("Primero abre una playlist en Spotify.")
                callback(None)
                return

            callback(m.group(1))

        self.web.page().runJavaScript(js, got_url)

    def rename_only_free(self):

        new_name = self.choose_name()

        def work(playlist_id):

            if not playlist_id:
                return

            try:
                client = sp()

                client.playlist_change_details(
                    playlist_id,
                    name=new_name
                )

                self.msg(f"Nombre cambiado gratis: {new_name}")
                self.web.reload()

            except Exception as e:
                self.msg(str(e))

        self.get_open_playlist_id(work)


    def activate_license(self):

        code, ok = QInputDialog.getText(
            self,
            "Activar Licencia",
            "Coloca tu código de activación:"
        )

        if not ok or not code.strip():
            return

        code = code.strip().upper()

        try:
            db = supabase_client()
            did = device_id()

            result = db.table("licenses").select("*").eq("code", code).execute()

            if not result.data:
                self.msg("Código no existe.")
                return

            lic = result.data[0]

            if lic.get("activated") and lic.get("device_id") != did:
                self.msg("Este código ya fue usado en otro equipo.")
                return

            now = datetime.now(timezone.utc)

            if not lic.get("activated"):
                days = int(lic.get("license_days", 7))
                expires = now + timedelta(days=days)

                db.table("licenses").update({
                    "activated": True,
                    "activated_at": now.isoformat(),
                    "expires_at": expires.isoformat(),
                    "device_id": did
                }).eq("code", code).execute()

            FILES["license"].write_text(code, encoding="utf-8")
            self.msg("Licencia activada correctamente.")
            self.update_usage_label()

        except Exception as e:
            self.msg("ERROR activando licencia:")
            self.msg(str(e))

    def get_license(self):

        if not FILES["license"].exists():
            return None

        code = FILES["license"].read_text(encoding="utf-8").strip()

        if not code:
            return None

        db = supabase_client()
        result = db.table("licenses").select("*").eq("code", code).execute()

        if not result.data:
            return None

        return result.data[0]

    def check_license_before_generate(self):

        try:
            lic = self.get_license()

            if not lic:
                self.msg("No tienes licencia activa. Presiona 🔐 Activar Licencia.")
                return False

            did = device_id()

            if lic.get("device_id") != did:
                self.msg("Licencia no pertenece a este equipo.")
                return False

            expires_at = lic.get("expires_at")

            if expires_at:
                exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)

                if now > exp:
                    self.msg("Licencia vencida.")
                    return False

            used = int(lic.get("used_playlists", 0))
            limit = int(lic.get("playlist_limit", 0))

            if used >= limit:
                self.msg("Límite de playlists alcanzado.")
                return False

            remaining = limit - used
            self.msg(f"Licencia OK. Playlists restantes: {remaining}")

            return True

        except Exception as e:
            self.msg("ERROR verificando licencia:")
            self.msg(str(e))
            return False

    def consume_license_use(self):

        try:
            lic = self.get_license()

            if not lic:
                return

            used = int(lic.get("used_playlists", 0)) + 1

            db = supabase_client()
            db.table("licenses").update({
                "used_playlists": used
            }).eq("code", lic.get("code")).execute()

            self.msg(f"Uso registrado. Playlists usadas: {used}")
            self.update_usage_label()

        except Exception as e:
            self.msg("No pude registrar uso licencia:")
            self.msg(str(e))

    def generate_playlist(self):

        try:

            if not self.check_license_before_generate():
                return

            self.update_library()

            songs = read(FILES["library"])

            if not songs:
                self.msg("No hay canciones.")
                return

            client = sp()

            random_library = []

            try:
                db = supabase_client()
                rq = db.table("random_queries").select("query").eq("active", True).execute()
                queries = [x["query"] for x in rq.data if x.get("query")]
            except Exception:
                queries = ["top hits", "viral music", "latin hits", "reggaeton", "pop hits", "dance hits"]

            for q in queries:

                try:

                    results = client.search(
                        q=q,
                        type="track",
                        limit=10,
                        market="US"
                    )

                    for t in results.get("tracks", {}).get("items", []):

                        if t.get("id"):

                            random_library.append(
                                f"https://open.spotify.com/track/{t['id']}"
                            )

                except Exception as e:

                    self.msg(str(e))

            random_library = list(dict.fromkeys(random_library))

            total = random.randint(50, 60)

            mine_percent = random.randint(80, 90) / 100

            mine_count = int(total * mine_percent)

            random_count = total - mine_count

            used = set(read(FILES["used"]))

            mine_fresh = [x for x in songs if x not in used]

            if len(mine_fresh) < mine_count:
                mine_fresh = songs

            random_fresh = [x for x in random_library if x not in used]

            if len(random_fresh) < random_count:
                random_fresh = random_library

            selected_mine = random.sample(
                mine_fresh,
                min(mine_count, len(mine_fresh))
            )

            selected_random = random.sample(
                random_fresh,
                min(random_count, len(random_fresh))
            )

            selected = selected_mine + selected_random

            missing = total - len(selected)

            if missing > 0:

                extra_pool = [
                    x for x in random_library + songs
                    if x not in selected
                ]

                if extra_pool:

                    selected += random.sample(
                        extra_pool,
                        min(missing, len(extra_pool))
                    )

            selected = selected[:total]

            random.shuffle(selected)

            write(FILES["generated"], selected)

            append(FILES["used"], selected)

            self.msg(f"Generadas {len(selected)} canciones")

            new_name = self.choose_name()

            js = "window.location.href;"

            def callback(current_url):

                self.msg(f"Playlist abierta: {current_url}")

                m = re.search(
                    r"/playlist/([A-Za-z0-9]+)",
                    current_url
                )

                if not m:

                    self.msg("Primero abre una playlist.")
                    return

                playlist_id = m.group(1)

                try:

                    client2 = sp()

                    client2.playlist_change_details(
                        playlist_id,
                        name=new_name
                    )

                    self.msg(f"Nombre cambiado: {new_name}")

                    track_uris = []

                    for link in selected:

                        m2 = re.search(
                            r"track/([A-Za-z0-9]+)",
                            link
                        )

                        if m2:

                            track_uris.append(
                                f"spotify:track:{m2.group(1)}"
                            )

                    if track_uris:

                        client2.playlist_add_items(
                            playlist_id,
                            track_uris
                        )

                        self.msg(f"Canciones agregadas API: {len(track_uris)}")

                        playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"

                        append(
                            FILES["created_playlists"],
                            [playlist_url]
                        )

                        self.consume_license_use()

                        self.web.reload()

                except Exception as e:

                    self.msg(str(e))

            self.web.page().runJavaScript(
                js,
                callback
            )

        except Exception as e:

            self.msg(str(e))


app = QApplication(sys.argv)

app.setStyle("Fusion")

window = App()

window.show()

sys.exit(app.exec())
