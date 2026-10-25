# supadata-transcript-search

Find the moment in a YouTube video where something was said. This is a one-file command line tool: `add` fetches timestamped captions for the videos you give it and stores them in a local SQLite full-text index, and `search` returns ranked passages with a `youtu.be` link that opens each video at the matching second.

Transcripts come from [Supadata](https://supadata.ai/r/5BK3TDWN) through the official `supadata` Python SDK. Search runs offline on SQLite's FTS5 extension, with no vector database, no embedding model and no server.

Disclosure: the supadata.ai/r/5BK3TDWN link is my referral link. If you sign up through it, I earn Supadata credits.

## Install

Python 3.10 or newer, with an SQLite build that includes FTS5 (most do).

```bash
pip install -r requirements.txt
export SUPADATA_API_KEY="your-key"
```

Create the key at [dash.supadata.ai](https://dash.supadata.ai). The script reads it from the environment and never prints it. Only `add` needs it.

## Usage

### add

Index one or more videos. Full URLs, `youtu.be` links, Shorts links and bare 11-character video ids all work.

```bash
python transcript_search.py add \
  "https://www.youtube.com/watch?v=A3-qLhe46Dw" \
  "https://youtu.be/rSKwyE5_EJA" \
  --max-calls 2
```

Real output:

```text
indexed  A3-qLhe46Dw lang=en chunks=33
indexed  rSKwyE5_EJA lang=en chunks=60
api_calls: 2
```

- Each new video is one Supadata request for native captions (`mode="native"`), merged into passages of about 300 characters.
- Videos already in the index are skipped without a request, so rerunning with a longer list only pays for the new ones.
- `--max-calls` (default 5) stops the run before it makes more requests than you meant to. `--lang` (default `en`) sets the preferred caption language.
- A video without captions is reported and skipped.

### search

```bash
python transcript_search.py search "memory OR remember" --limit 3
```

Real output:

```text
rSKwyE5_EJA @ 1:03  https://youtu.be/rSKwyE5_EJA?t=63
    ... and the cool thing is like the the the the computers [remember] this stuff, right? The the agents ...
A3-qLhe46Dw @ 7:34  https://youtu.be/A3-qLhe46Dw?t=454
    can describe anything that Grok bots can do, which those include routines, secrets skills [memories] importantly and under ...
rSKwyE5_EJA @ 7:52  https://youtu.be/rSKwyE5_EJA?t=472
    ... the the storage that you have or the [memory] that you have, sometimes these bots can can can ...
```

Queries use FTS5 syntax: plain words are ANDed, `OR` widens the match, and double quotes search for a phrase. Results are ranked with `bm25()`, and the matched words are shown in brackets. English stemming is on, so `memory` also matches "memories". `--limit` defaults to 5.

The index lives in `transcripts.db` next to the script. Delete it to start over.

## Limits

- Keyword search, not semantic search. It matches words and their stems, not meaning.
- Captions only. Generated transcripts (`mode="auto"`) are priced differently; see [Supadata pricing](https://supadata.ai/pricing) before switching.
- One request at a time with no retry, which suits a handful of videos rather than whole channels.

## License

MIT. See [LICENSE](LICENSE).
