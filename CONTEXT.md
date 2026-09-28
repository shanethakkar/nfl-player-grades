# NFL Player Grades

Grades every NFL player's season on a 0–100 scale from public advanced stats, within position.

## Language

### Grading

**Grade**:
A 0–100 rating of a player's season performance *attributable to the player*: credit for what the player controls, with QB, scheme and team context stripped where it can be measured. A description of the season, not a talent forecast.
_Avoid_: rating, score, talent grade, PFF grade

**Component**:
One per-play rate stat that feeds a position's **Grade** (e.g. EPA per dropback, target earn rate).
_Avoid_: metric, feature, stat (when meaning a formula input)

**Candidate**:
A proposed **Component** under evaluation that is not yet in any formula.

**Formula**:
The set of **Components** and signed weights for one position.
_Avoid_: model, algorithm

**Composite**:
The weighted combination of a player's **Component** z-scores, standardized so that a given **Grade** means the same percentile at every position and season.

**Qualified**:
A player-season with enough volume to rank on the leaderboard and to define the comparison group for its position-season.
_Avoid_: eligible, starter

**Provisional grade**:
A **Grade** for a season still in progress, computed from games through a stated week and restated every week until the season ends.
_Avoid_: live grade, partial grade, weekly grade

**Through week**:
The last completed regular-season week included in a **Provisional grade**.

### Evaluation

**Reliability**:
How much of a **Grade** or **Component** is signal rather than sampling noise within one season, measured odd weeks vs. even weeks.
_Avoid_: stability, consistency

**Portability**:
How well a **Grade** or **Component** carries over for players who change teams year to year: the test that it measures the player rather than the team.
_Avoid_: stickiness

**Opponent adjustment**:
Removing the strength of the defenses (or offenses) a player faced from a **Component**.
_Avoid_: schedule adjustment, SOS adjustment
