"""Model ladder for every AI call (user sign-off 2026-10-25).

Each call starts with the cheapest model and moves up only when needed:

    claude-haiku-5-5 -> claude-sonnet-5-5 -> claude-opus-5-5 -> claude-fable-5-1

A model's answer is accepted when it passes the caller's own checks (shape,
formats) and its self-reported confidence is at least THRESHOLD. Otherwise
the next model is asked. If no model passes, the most confident valid answer
is kept and flagged LOW_MODEL_CONFIDENCE (lowers the case's score in
output_confidence.csv); if no model answers at all, ALL_MODELS_FAILED.

A model's confidence about itself is not well calibrated, so it is one signal
next to the caller's checks, never the only one. Every rung is cached per
model and prompt version by the caller, so reruns follow the same ladder and
give the same answer; the attempts are returned for the trace and the usage
report.
"""
LADDER = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-1")
THRESHOLD = 0.90


def escalate(call, check=lambda answer: [], models=LADDER, threshold=THRESHOLD):
    """call(model) -> cache entry ({"answer", "usage", ...} or {"error"}).
    check(answer) -> list of problems (empty when the answer is acceptable).
    Returns {"answer", "model", "confidence", "attempts", "flags"}."""
    attempts, best = [], None
    for model in models:
        entry = call(model)
        answer = entry.get("answer")
        problems = check(answer) if answer is not None else []
        confidence = answer.get("confidence") if answer is not None else None
        passed = answer is not None and not problems and confidence is not None and confidence >= threshold
        attempts.append({"model": model, "confidence": confidence, "passed": passed,
                         "problems": problems, "error": entry.get("error", ""),
                         "usage": entry.get("usage", {})})
        if answer is not None and not problems and (best is None or confidence > best[2]):
            best = (model, answer, confidence)
        if passed:
            return {"answer": answer, "model": model, "confidence": confidence,
                    "attempts": attempts, "flags": []}
    if best:
        return {"answer": best[1], "model": best[0], "confidence": best[2],
                "attempts": attempts, "flags": ["LOW_MODEL_CONFIDENCE"]}
    return {"answer": None, "model": "", "confidence": None, "attempts": attempts,
            "flags": ["ALL_MODELS_FAILED"]}
