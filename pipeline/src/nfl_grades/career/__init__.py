"""Career grades: Kalman-style recency-weighted smoothing across seasons.

Each season grade is treated as a noisy observation of an evolving true skill.
A 1D Kalman filter gives us a posterior mean (career grade) and posterior
variance (uncertainty) which the UI surfaces as `93 +/- 4`.

Two tunable parameters:
    tau_sq : process noise (how fast skill can change year over year)
    r_sq   : observation noise (from the season grade's own confidence)

To be implemented in build step 8.
"""
