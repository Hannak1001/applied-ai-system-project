# 🎧 Model Card: VibeMatch

## 1. Model Name

**VibeMatch** (this version builds on **VibeMatch 1.0**, my Module 1–3 *Music Recommender Simulation*).

VibeMatch 1.0 was a scoring function over 20 hand-written songs. This version is a system of several parts: a conversational agent, retrieval over ~8,000 real songs, the original scorer, and grounded, verified explanations.

---

## 2. Goal / Task

VibeMatch suggests songs a listener might like and says *why*. It does not predict a rating. A user describes what they want in plain English ("late night studying, something calm"). The system builds a small taste profile (mood, genre, energy, acoustic preference, how familiar the songs should be), retrieves matching songs, ranks them, and explains each pick using only facts from the data. The user can then steer with chat or thumbs up and down.

---

## 3. Data Used

- **Catalog:** `data/catalog.csv`, 7,908 songs built from the Kaggle *Spotify Tracks Dataset* (114k rows, 114 genres). [src/data_prep.py](src/data_prep.py) removes duplicate tracks (keeping the most popular copy), then keeps up to **70 songs per genre** so no genre dominates.
- **Per-song fields:** title, artist, genre, mood, energy, tempo, valence, danceability, acousticness, popularity.
- **Moods are derived, not given.** The dataset has no mood column, so I assign one of eight moods (happy, energetic, intense, chill, focused, melancholy, romantic, moody) from valence, energy, acousticness and instrumentalness using hand-written rules. These are heuristics. They are my interpretation of what the numbers feel like, not human labels.
- **Album art and previews** come from Deezer's public search API at runtime (song title and first artist are sent; nothing about the user is).
- **User data:** chats are saved only in a local file (`data/chats.json`, git-ignored). When a Gemini key is set, the user's chat messages and the retrieved song metadata are sent to Gemini; no account, name or contact detail is collected or sent.
- The data has no lyrics, no language field, and no real listening history.

---

## 4. How the System Works

| Stage | What it does | AI or code? |
|---|---|---|
| **Agent** | Asks adaptive questions only until it knows the mood or activity, then builds a `UserProfile` and refines it from feedback. | Gemini reads messy language (JSON mode); a keyword extractor does the same job offline. Question logic is code. |
| **Retrieval (RAG)** | Filters the catalog by mood, genre, energy window and popularity. If fewer than 12 songs match, it relaxes one filter at a time and records which. | Code |
| **Scorer** | The original VibeMatch 1.0 score out of 100: mood 35, genre 25, energy closeness 25, acousticness 15. At most one song per artist. | Code (explainable, deterministic) |
| **Generation (RAG)** | One sentence per song, written from the retrieved facts only. | Gemini |
| **Verifier** | Checks every number, mood, genre and descriptor in the sentence against the data. A failing sentence is replaced by a template. | Code |
| **Feedback** | "More upbeat", "calmer", "less acoustic", "more familiar", "hidden gems", a new request, or thumbs up and down. | Code, with Gemini reading free text |

Why this split: the model handles language, and ordinary code handles anything that has to be *true* or *repeatable*. Every AI call has an offline fallback, so a missing key, a rate limit, or a bad reply degrades the experience but never breaks it.

---

## 5. Observed Behavior / Biases

- **Genre requests are often only partly honored.** Because each genre has just 70 songs, most genre-plus-mood combinations are thin: 39 of 56 combinations in my evaluation have fewer than 12 songs. Retrieval then relaxes the genre first, so a user who asks for "classical, intense" mostly gets other genres. Only 13 of 56 genre requests returned six songs of the requested genre (34% of picks matched overall).
- **Derived moods can feel wrong.** "Focused" is mostly instrumental tracks, so studying can return tango or classical. Valence and energy are a crude proxy for feeling, and they carry assumptions that don't hold equally across cultures and musical styles.
- **Exact-label scoring from v1 still applies.** Mood and genre get all-or-nothing points, so a song that sounds right but is labeled differently can lose to one with the right label.
- **Defaults can look like preferences.** If a user only names a mood, energy and acoustic taste are filled with defaults. I found the explanations originally called these defaults "your target" and fixed it (explanations now say "the medium level I assumed" or leave it out).
- **Filter bubble risk.** The scorer rewards exact matches, so repeat requests get similar songs. I added a one-song-per-artist rule, and with no genre chosen, the picks spread across 32 genres (top 5 genres = 38%), but the mood match is still tight (100% in evaluation).
- **Popularity.** Recommended songs are slightly *less* popular than the catalog average (46.2 vs 51.2), so the system isn't just pushing hits. "More familiar" raises the popularity floor in steps (median 48 → 68 in one test) and "hidden gems" caps it.
- **Catalog skew.** The catalog reflects the Kaggle dataset: it contains many languages and regions, but only what that dataset sampled. A 70-song cap is not a fair picture of any genre.
- **Single-profile limit.** One mood, one genre and one energy target can't represent mixed tastes. "Pop with a mix of classic rock" keeps one genre.
- **Previews depend on Deezer.** Some songs have no cover or preview there, so those cards show a placeholder. Previews are only a convenience; the recommendation does not depend on them.

---

## 6. Evaluation Process

**Automated tests: 74.** They cover agent extraction and feedback, retrieval and relaxation, the verifier (including a mocked Gemini that returns bad output), chat saving (including a corrupt file), the stats, Deezer matching, and the whole Streamlit app driven headlessly (answering, Home button, thumbs, saved chats).

**Offline evaluation** (`python -m src.evaluate`, no network or key): 64 profiles (8 moods × 8 genre choices), top 6 each.

| Measure | Result |
|---|---|
| Full set of 6 picks returned | 100% |
| Picks matching requested mood | 100% |
| Avg distinct artists in the 6 picks | 6.0 |
| Avg distance from target energy | 0.020 |
| Template explanations passing the grounding check | 100% |
| Picks matching requested genre | **34%** |
| Profiles retrieved without relaxing a filter | **31%** |

**Grounding verifier, adversarial check.** I wrote 10 explanations that should be rejected and 3 that should pass. The verifier rejected **7 of 10** bad ones and wrongly rejected **0 of 3** good ones. It *missed* three claims that contain no numbers or catalog words: "the singer's powerful voice shines", "a prominent piano melody", and "the sad lyrics will resonate". The verifier checks claims against the data, so it cannot catch invented prose it has no data to compare with. The prompt forbids such claims, but the verifier does not enforce it.

**Live Gemini spot check.** On four profiles (20 explanations) with `gemini-3.5-flash-lite`, all 20 passed the verifier, including honest ones like "does not match the requested genre of opera, but does match the happy mood". This is a small sample, not a guarantee.

**Manual checks in a real browser** (Chrome via Playwright): one preview plays at a time, no screen flicker on thumbs, the page loads at the top, saved chats reopen.

**What the evaluation changed.** It showed template explanations failing their own check 2% of the time (a dataset genre literally named "chill" tripped the mood rule), and reading the sample outputs revealed the "defaults presented as preferences" problem above. Both were fixed and are covered by tests.

*(VibeMatch 1.0 was evaluated on three hand-built profiles (pop, rock, lofi) over 20 songs. Its main finding, that the mood and genre weights decide almost every result, still holds for the scorer used here.)*

---

## 7. Intended Use and Non-Intended Use

**Intended use**

- A portfolio and classroom project showing how to combine an LLM, retrieval and ordinary code reliably.
- Casual music discovery by mood, with clear reasons for each pick.
- Learning how scoring weights, retrieval and grounding shape recommendations.

**Not intended for**

- A real music service with real users. The catalog is small, the moods are heuristics, and there is no listening history.
- Deciding what artists get heard or paid.
- Judging a person's taste or inferring anything about them. It sees a handful of stated preferences.
- Anything where a wrong explanation would cause harm. The verifier reduces, but does not remove, the chance of an unsupported claim.

---

## 8. Responsible AI: Risks and Safeguards

- **Hallucination.** The LLM is only given retrieved facts and told to use nothing else, then every sentence is verified, and failures fall back to a template. Known gap: invented prose with no numbers or catalog words can pass (see Evaluation).
- **Prompt injection.** Song titles and artist names are untrusted text from a dataset. They are passed to Gemini as data with an explicit instruction never to follow instructions inside them, and they are HTML-escaped before display. I did not test against adversarial song titles, so this is a design safeguard, not a tested guarantee.
- **Secrets and privacy.** The API key lives in a git-ignored `.env`. Chats stay on the local machine. The only user text that leaves the machine is the chat message sent to Gemini when a key is configured.
- **Reliability.** Free-tier quotas ran out repeatedly during development. Fallbacks mean the app keeps working, and a short cooldown after a quota error avoids slow repeated failures.
- **Honesty about defaults and mismatches.** Explanations don't present system defaults as the user's preferences, and they say so when a song doesn't match the requested genre or mood. The UI also tells the user when retrieval had to widen the search.

---

## 9. Limitations

- Moods are my heuristic labels, not ground truth, and they may fit some music (and some cultures) better than others.
- Genre-specific requests are frequently only partly met, because of the 70-song-per-genre cap and relaxing genre before mood.
- The verifier can't catch outside-knowledge claims that contain no numbers or catalog words (3 of 10 adversarial cases missed).
- One profile can't represent mixed tastes, and there is no memory of taste across chats beyond the stats panel.
- Quality depends on the free Gemini tier. Without it, language understanding is keyword-based (it handles common phrases, not subtle ones) and explanations are templated.
- Cover art and previews depend on Deezer having the track.
- Evaluation is offline and small. There was no study with real listeners, so "good recommendation" is measured by consistency with the stated request, not by whether people enjoyed the songs.

---

## 10. Ideas for Improvement

1. **Relax mood before genre when the user named a genre.** An explicit genre is stronger evidence than my derived mood. The evaluation shows the current order is the main reason genre requests fail.
2. **Raise or remove the per-genre cap**, or sample by genre *and* mood, so more combinations have enough songs.
3. **Strengthen the verifier**: allow only claims drawn from a whitelist of fields, or add a second model as a judge for unsupported prose.
4. **Support mixed tastes** with multiple genres or weighted profiles.
5. **Use better mood signals** (human tags such as Last.fm, or lyrics) instead of valence and energy alone, and add embedding-based retrieval for vague requests.
6. **Evaluate with real listeners** instead of only against the stated request.

---

## 11. AI Collaboration and Personal Reflection

**How I worked with AI.** I used an AI coding assistant (Claude Code) as a pair programmer for the whole upgrade. We planned the architecture first (the diagram), then built it in stages: the agent, retrieval, reusing my original scorer, grounded explanations, feedback, and finally the UI. The AI wrote most of the code and tests. I made the product decisions (free tools only, the look and feel, the layout, chat history, thumbs behavior) and tested by actually using the app, which turned out to matter more than the code review.

**A suggestion I accepted.** The AI suggested using **Gemini's free tier with a rule-based fallback**, instead of depending on Gemini alone (or on a paid or key-gated service like Spotify). I accepted it. It paid off almost immediately: the free quota ran out many times while I was building, and the app kept working with keyword extraction and template explanations. The fallback also let the whole test suite run offline.

**A suggestion I rejected, and one I sent back.**
- *Rejected:* the AI offered a Spotify-green or Apple-blue accent for the dark UI. I said no to both. I didn't want a trademarked color, and I didn't want it to look "AI" (no purple either). I asked for a monochrome base with warm hues for close matches and cool hues for weaker ones, and that became the match-strength color scale.
- *Revised after I tested it:* the AI's first onboarding asked up to four questions before showing any songs. When I ran it, it never recommended anything, because it was still waiting on the last question after I'd already said "recommend me some romantic music." I reported it, and the agent was changed to recommend as soon as it knows the mood and refine afterward.

**When I (and the checks) caught the AI being wrong.** The AI stated that templates always pass the grounding check, and its own unit test agreed. My evaluation script showed 98%, which led to the "chill" genre bug. Reading real sample outputs revealed that explanations claimed preferences I never gave. It also picked a Gemini model that Google had retired for new users, and used an API version that didn't support JSON mode. A hidden header made the top bar unclickable, which no unit test noticed and only a real browser run did. The lesson was that AI-written code can sound finished and be slightly wrong, so reading the output was my job.

**Biggest learning moment.** In VibeMatch 1.0 it was that the weights are the design: mood 35 and genre 25 decided nearly every result. In this version it was that the engineering around the model matters more than the model: retrieval to narrow the facts, a verifier to reject ungrounded text, fallbacks for every AI call, and tests that don't need a network.

**What surprised me.** How much the evaluation told me that passing tests didn't. All the tests were green while the genre match rate was only 34%, and the offline evaluation was the first thing to say so.

**What I would try next.** The improvement list above, starting with relaxing mood before genre, because the numbers say it is the biggest fix.
