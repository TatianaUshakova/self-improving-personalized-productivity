## Sample Task 1: Reconstruct a day of product research, errands, and communication

**Scenario**: You are given one day's worth of browser history, map activity, call logs, and todos for a single user. The traces include research browsing across documentation sites and GitHub repositories, a family phone call, a short errand, and evening planning activity.

**Goal**: Produce a 15-minute timeline with detailed freeform labels such as:

- `called sister`
- `went out to get matcha`
- `reading available docs and research-relevant GitHub repos for a budgeting app`
- `planned tomorrow's tasks and priorities`

**Important properties**:

- Labels should preserve intent, not just a broad category.
- The same website can mean different things at different times.
- Browser events may need deduplication and session merging before they are useful.

---

## Sample Task 2: Distinguish trip planning from actual movement

**Scenario**: The user repeatedly opens Google Maps during the day. Some map sessions happen while stationary at home and look like planning future travel; other map activity aligns with real movement and location transitions.

**Goal**: Reconstruct the timeline so that map usage is interpreted correctly in context, for example:

- `used Google Maps to plan an evening trip`
- `traveled from home to a cafe`
- `attended the Luma BBQ event`

**Important properties**:

- Do not label all map activity as travel.
- Cross-check location traces, timestamps, and neighboring browser sessions.
- Preserve transitions when the evidence supports them.

---

## Sample Task 3: Infer project intent from LLM chat titles and surrounding context

**Scenario**: The browser history contains several ChatGPT or Claude conversations with titles that hint at the user's true intent, alongside GitHub repositories, docs, and email.

**Goal**: Produce labels that recover the specific project being worked on rather than generic descriptions such as `used ChatGPT` or `worked`.

Prefer labels like:

- `brainstormed edge cases for a budgeting app using LLM chats and nearby repo context`
- `compared implementation approaches across documentation and relevant GitHub repositories`

**Important properties**:

- LLM usage is evidence, not the activity label itself.
- Nearby tabs and repeated revisits often reveal the real task.
- The best label usually combines multiple signals into one coherent activity.

---

## Sample Task 4: Capture both the main event and the immediate follow-up

**Scenario**: The day contains a clearly bounded interview or meeting, followed by short notes, follow-up browsing, and a shift into a different task.

**Goal**: Produce labels that preserve that structure, for example:

- `AeroVect interview`
- `AeroVect interview, followed by a short note about what was discussed`
- `returned to budgeting app research after the interview`

**Important properties**:

- Preserve meaningful transitions rather than flattening them into one vague block.
- Short post-event note-taking can be important enough to label distinctly.
- The best timeline explains what happened immediately before and after the main event.
