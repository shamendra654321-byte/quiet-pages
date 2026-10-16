## Change reading speed while you listen

The speed control now takes effect during playback: no Stop and Play needed. Change from 0.5x to 2x while listening, and the current audio adjusts without restarting the passage. The narrator's pitch is preserved. Paused playback stays paused, with the new speed ready when you resume.

Quiet Pages now generates speech at its normal speed and changes tempo during playback. Prepared chapters and saved recordings can be reused at different speeds, without waiting for another voice generation. Word highlighting and seeking follow the original recording position as tempo changes. Rewind uses 15 seconds at the currently selected speed.

Speed changes are applied in small audio blocks; sound already queued to your output device must finish first. Bluetooth or other high-latency devices may make the change take longer to hear. Extreme speeds can introduce some audio-processing artifacts. Existing normal-speed cached audio is reused; older cache entries generated at other speeds are no longer needed and expire normally.

46 automated tests passed, including live speed changes in one stream, pitch preservation, duration, the final audio frame, invalid input and pause/position preservation. The Windows release workflow also tests the installed app with real voices, live tempo changes, cached replay and scanned PDFs before publishing.

Update inside Quiet Pages: Help → Check for updates → download → Restart to update.

Download page: https://quiet-pages.abuzzlion9.chatgpt.site
