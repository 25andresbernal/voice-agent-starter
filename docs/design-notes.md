# Design notes: why direct SIP instead of a wrapper

This starter routes calls through Twilio Elastic SIP Trunking straight into
OpenAI's Realtime API over SIP. That is a deliberate choice against two more
common architectures, and it is worth writing down why, because the
tradeoff only becomes obvious once you have shipped a voice agent and had
to debug it at 11pm.

## The three architectures

**1. Media Streams over WebSocket.** Twilio's `<Connect><Stream>` verb
opens a WebSocket and streams call audio to your own server as base64-
encoded mu-law frames. Your server decodes the audio, sends it to a
speech-to-speech model (or a transcription model), gets audio back, and
streams it back to Twilio. This is the most common pattern in tutorials
because it is flexible: your server sits in the middle of every frame and
can do anything it wants with the audio.

**2. A voice-agent wrapper platform.** A hosted layer sits between the
telephony provider and the model: it owns speech-to-text, text-to-speech,
turn-taking, and the LLM call, and exposes a simpler API and dashboard.
This is the fastest way to get a first call working.

**3. Direct SIP into a speech-to-speech Realtime API.** The telephony
provider's SIP trunk is pointed directly at the model provider's own SIP
endpoint. Your server never touches raw audio; it receives a webhook that
a call is ringing, accepts it with a session configuration, and then opens
a WebSocket purely to observe events and handle tool calls. This is what
this repository implements, documented in `README.md` and built in
`src/voice_agent/realtime_client.py`.

## The latency budget

A phone conversation has a turn-taking budget of a few hundred
milliseconds before a pause reads as awkward. Every hop that raw audio
crosses on the way to a model and back eats into that budget:

- Media Streams: Twilio to your server (network hop), your server decodes
  and buffers frames, your server to a transcription model, transcript to
  an LLM, LLM text to a TTS model, TTS audio back through your server, your
  server to Twilio. That is at minimum two extra network hops and three
  extra model calls beyond the conversation model itself, each with its
  own queueing and cold-start behavior.
- A wrapper platform: your server is now a *fourth* party in the loop
  (telephony provider, wrapper platform, model provider, your server) even
  though your server does none of the audio work. Every round trip adds
  the wrapper's own queueing.
- Direct SIP: the telephony provider and the model provider's speech-to-
  speech endpoint talk to each other directly over SIP. Your server is not
  in the audio path at all; it only sees text-level events (transcripts,
  function calls) over a control WebSocket. Two hops are simply removed
  from the audio path, because there are two fewer systems for the audio
  to transit.

Removing hops does not just save milliseconds in the average case, it
removes entire classes of tail latency: a slow transcription call, a
congested TTS queue, or a wrapper platform's own rate limiting can each
independently blow the turn-taking budget in the first two architectures.
In the direct-SIP architecture those failure modes do not exist, because
those systems are not in the path.

## Turn-taking failure modes this design avoids

Chaining a text LLM behind a separate speech-to-text and text-to-speech
layer produces specific, repeatable failure modes, independent of which
LLM or TTS voice you pick:

- **Monologuing.** A model trained mostly on turn-based chat text, prompted
  to "be helpful," tends to produce long, complete answers. On a phone call
  a long answer is not "complete," it is a wall of audio the caller cannot
  interrupt without an explicit interruption-handling layer, and cannot
  hold in their head even if they let it finish. This is why the eval
  harness in `evals/scorecard.py` scores average assistant turn length as
  a first-class metric.
- **Premature closes.** A model that cannot hear the caller's tone (because
  it only sees a text transcript) has no signal that the caller is
  hesitant, confused, or about to ask a follow-up. It closes the call as
  soon as the transcript looks like a plan was agreed to. The scorecard's
  "no premature close" check exists because this is a silent failure: the
  call ends, the log looks fine, and the caller is the only one who knows
  it went wrong.
- **No mirroring.** Natural phone conversation involves short
  acknowledgments, confirming back what was heard, and matching the
  caller's pace. A model that receives a flat transcript and must generate
  a flat transcript back has no channel for this; the result reads as
  correct but robotic, which callers notice even when they cannot name
  why.

A speech-to-speech model that hears the actual audio (tone, pace,
hesitation) and speaks the actual audio back does not fix these failure
modes by itself, but it removes the specific cause that a text-only
round trip forces on the system: the total loss of paralinguistic
information at the STT boundary, twice per turn.

## Why debugging a wrapper platform is hard

A self-hosted or fine-tuned model behind a third-party wrapper platform
means every layer that could be the source of a bad call is opaque from at
least one side. When a call goes wrong, the questions you need to answer
are: did the transcription mishear the caller, did the model produce a bad
response, did the TTS clip the audio, or did the wrapper's own turn-taking
logic cut someone off? With a wrapper platform in the middle, you typically
get one merged log, if you get logs at all, and no way to independently
replay just the model's turn on the same input. Debugging becomes
guessing which layer to blame from call-quality symptoms alone, then
opening a support ticket to confirm it.

A direct integration inverts this: you own the webhook, you own the
WebSocket, and you write out the transcript in a format you control (see
`src/voice_agent/transcript.py`). Every tool call, every model turn, and
every timestamp is in one file in `transcripts/`, in your own repository,
replayable by anyone with the JSONL. That is also what makes the eval
harness possible at all: `evals/scorecard.py` cannot score a call it never
gets a clean transcript for.

## Why this starter still documents Media Streams

Direct SIP is not strictly better in every case. If you need custom DSP on
the audio (your own VAD, a compliance recording pipeline with specific
codec requirements, or a non-OpenAI model that only accepts raw audio),
Media Streams over WebSocket is still the right tool, because it puts your
server in the audio path on purpose. The tradeoff this starter makes is
specific to the case where the model provider offers a SIP endpoint and
you do not need to touch the raw audio: in that case, staying out of the
audio path is a win with no real downside.
