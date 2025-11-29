# RAG Chatbot - Database-Only Mode

## 🎯 Übersicht

Das RAG-System verwendet jetzt **ausschließlich die MariaDB-Datenbank** für alle Operationen:
- ✅ Keine Abhängigkeit von `sample.txt` mehr
- ✅ Embeddings werden in der Datenbank gecached (17x schneller)
- ✅ Automatische Embedding-Generierung für neue Einträge
- ✅ Unterstützung für Projekt- und User-Retrieval

## 🚀 Setup

### 1. Datenbank initialisieren

Die Datenbank wird automatisch mit Embedding-Support initialisiert:

```bash
# Alte Datenbank-Daten löschen und neu initialisieren
docker compose down -v
docker compose up -d
```

Die `docker-compose.yml` nutzt jetzt automatisch `recsys_init_with_embeddings.sql`.

### 2. Daten von MongoDB synchronisieren

```bash
# Python-Environment aktivieren
.env/Scripts/activate  # Windows
# source .env/bin/activate  # Linux/Mac

# Daten synchronisieren und erste Embeddings generieren
python rag_chatbot.py --sync "Test query"
```

## 💡 Verwendung

### Basis-Verwendung (mit gecachten Embeddings)

```bash
# Schneller Start (nutzt DB-gecachte Embeddings)
python rag_chatbot.py "Zeige mir KI-Projekte"

# Englische Anfrage
python rag_chatbot.py "Show me projects about blockchain"
```

### Erweiterte Optionen

```bash
# MongoDB-Daten synchronisieren vor der Anfrage
python rag_chatbot.py --sync "Deine Frage"

# Embeddings neu generieren (nötig nach vielen Änderungen)
python rag_chatbot.py --regenerate "Deine Frage"

# Auch User in die Suche einbeziehen
python rag_chatbot.py --users "Wer interessiert sich für Machine Learning?"

# Kombiniert
python rag_chatbot.py --sync --users "Blockchain-Experten finden"
```

## 📊 Funktionsweise

### Workflow beim ersten Start

1. **MongoDB → SQL Sync** (`--sync` Flag)
   - Lädt Projekte, Users und Tags vom Backend
   - Speichert in MariaDB

2. **Embedding-Generierung**
   - System prüft welche Projekte/Users keine Embeddings haben
   - Generiert Embeddings via OpenAI API
   - Speichert Embeddings in DB

3. **Retrieval**
   - User-Query wird in Embedding umgewandelt
   - Cosinus-Ähnlichkeit mit allen gespeicherten Embeddings
   - Top-K relevanteste Ergebnisse

4. **Generation**
   - GPT-4 generiert Antwort basierend auf Kontext
   - Strukturierte JSON-Ausgabe

### Workflow bei späteren Starts (SCHNELL!)

1. **Embeddings aus DB laden** (0.2s statt 3.5s)
2. **Retrieval** - Sofortige Suche
3. **Generation** - GPT-4 Antwort
4. **Logging** - Speicherung in `chat_log`

## 🔄 Automatische Embedding-Updates

Die Datenbank hat **Trigger**, die automatisch erkennen, wenn Daten geändert werden:

```sql
-- Bei Updates von Projects werden Embeddings als "veraltet" markiert
-- needs_embedding_update = 1

-- Beim nächsten Sync werden nur veraltete Embeddings neu generiert
```

### Manuell Embeddings als veraltet markieren

```sql
-- Für ein spezifisches Projekt
UPDATE Projects SET needs_embedding_update = 1 WHERE _id = 'project_id';

-- Für alle Projekte (Force Regeneration)
UPDATE Projects SET needs_embedding_update = 1;
```

## 📁 Dateien

### Geänderte Dateien

- **`rag_chatbot.py`** - Neues DB-only System
- **`docker-compose.yml`** - Nutzt `recsys_init_with_embeddings.sql`
- **`db-init/recsys_init_with_embeddings.sql`** - Schema mit Embeddings

### Backup-Dateien

- **`rag_chatbot_old.py`** - Alte Version mit sample.txt Support
- **`rag_chatbot.py.backup`** - Weiteres Backup
- **`db-init/recsys_init.sql`** - Original-Schema ohne Embeddings

## 🎨 Beispiel-Ausgabe

```json
{
  "message": "Es gibt mehrere relevante KI-Projekte:\n\n1. Das 'Automatisierte Code-Review mit KI' Projekt nutzt KI zur Analyse von Code-Commits...",
  "projects": [
    {
      "_id": "673f4a1e2c1b3a001f8d9e25",
      "title": "Automatisierte Code-Review mit KI",
      "createdAt": "2024-08-28 11:00:00",
      "relevance_score": 0.508
    },
    {
      "_id": "673f4a1e2c1b3a001f8d9e21",
      "title": "KI-gestütztes Gesundheitsmonitoring",
      "createdAt": "2024-08-15 14:30:00",
      "relevance_score": 0.467
    }
  ]
}
```

## 🛠️ Troubleshooting

### "No projects have embeddings"

```bash
# Embeddings neu generieren
python rag_chatbot.py --regenerate "Test"
```

### "Database connection refused"

```bash
# Prüfe ob Docker läuft
docker ps

# Starte Container neu
docker compose restart mariadb
```

### "API sync failed"

- Prüfe ob das Backend läuft (Port 3000)
- Prüfe `bearer_token.py` Token

### Embeddings updaten nach Daten-Änderungen

```bash
# Neue Daten von MongoDB holen + Embeddings für neue Einträge
python rag_chatbot.py --sync "Query"

# Alle Embeddings neu generieren (bei vielen Änderungen)
python rag_chatbot.py --regenerate "Query"
```

## 📈 Performance

| Operation | Alte Version (sample.txt) | Neue Version (DB) |
|-----------|--------------------------|-------------------|
| Startup | 3.5s | 0.2s (17x schneller) |
| Kosten pro Start | $0.0003 | $0.00 (gecached) |
| Datenquelle | Text-File | MariaDB |
| User-Support | ❌ | ✅ |
| Embedding-Cache | ❌ | ✅ |

## 🔐 Datenbank-Schema

Die erweiterte Datenbank enthält:

```sql
Projects:
  - embedding (JSON) - 1536-dim Vektor
  - embedding_model (VARCHAR) - Model-Name
  - needs_embedding_update (TINYINT) - Update-Flag
  - embedding_updated_at (DATETIME) - Timestamp

Users:
  - embedding (JSON)
  - embedding_model (VARCHAR)
  - needs_embedding_update (TINYINT)
  - embedding_updated_at (DATETIME)
```

## 🚀 Next Steps

1. **Integration in API**: `main.py` anpassen um RAG-System zu nutzen
2. **Background-Job**: Automatisches Updaten veralteter Embeddings
3. **Caching**: Redis für Query-Caching hinzufügen
4. **Monitoring**: Embedding-Qualität und Response-Zeiten tracken

## 📚 Weitere Dokumentation

- `VECTOR_EMBEDDINGS_GUIDE.md` - Detaillierte Embedding-Integration-Anleitung
- `db-init/recsys_init_with_embeddings.sql` - Schema mit Kommentaren
