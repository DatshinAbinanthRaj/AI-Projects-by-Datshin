"""Synthetic eight-week operations log. Nothing here comes from a real project.

Each queue is simulated day by day: tasks arrive on weekdays, the team has a
daily capacity in minutes, and tasks are worked oldest first. Three problems
are planted on purpose (see PLANTED).
"""
import random
from datetime import datetime, timedelta

import pandas as pd

START = datetime(2026, 8, 31)        # a Monday
WEEKS = 8
HOURS_PER_WEEK = 37.5

QUEUES = {
    #                      arrivals/day, minutes/task, SLA hours, annotators, cost/hour, QA pass
    "text_classification": dict(arrivals=190, minutes=5.0, sla=48, staff=3, cost=16.0, qa=0.95),
    "llm_response_rating": dict(arrivals=78, minutes=12.0, sla=72, staff=3, cost=22.0, qa=0.94),
    "image_bounding_box": dict(arrivals=100, minutes=9.0, sla=72, staff=3, cost=18.0, qa=0.93),
}
PLANTED = [
    "text_classification, week 3: one annotator absent (paid hours and capacity down by a third)",
    "llm_response_rating, weeks 5-6: QA pass rate falls to about 80% and rework doubles",
    "image_bounding_box, weeks 6-8: arrivals 45% higher with no extra staff",
]
PRODUCTIVE_SHARE = 0.80              # share of paid time spent on tasks
QA_SAMPLE_RATE = 0.15


def generate(seed=5):
    rng = random.Random(seed)
    tasks, workforce = [], []
    for queue, cfg in QUEUES.items():
        staff = [f"{queue[:3]}_{i}" for i in range(1, cfg["staff"] + 1)]
        waiting = []                 # tasks not yet worked, oldest first
        number = 0
        for week in range(1, WEEKS + 1):
            monday = START + timedelta(weeks=week - 1)
            present = staff[:-1] if (queue == "text_classification" and week == 3) else staff
            for person in staff:
                workforce.append({"week_start": monday.strftime("%Y-%m-%d"), "annotator_id": person,
                                  "queue": queue, "hourly_cost": cfg["cost"],
                                  "paid_hours": HOURS_PER_WEEK if person in present else 0.0})
            surge = 1.45 if (queue == "image_bounding_box" and week >= 6) else 1.0
            bad_qa = queue == "llm_response_rating" and week in (5, 6)
            for day in range(5):
                date = monday + timedelta(days=day)
                for _ in range(max(0, round(rng.gauss(cfg["arrivals"] * surge, cfg["arrivals"] * 0.08)))):
                    number += 1
                    created = date + timedelta(hours=7, minutes=rng.randint(0, 9 * 60))
                    waiting.append({"task_id": f"{queue[:3].upper()}-{number:05d}", "queue": queue,
                                    "created_at": created, "due_at": created + timedelta(hours=cfg["sla"])})
                waiting.sort(key=lambda t: t["created_at"])
                minutes_left = len(present) * HOURS_PER_WEEK / 5 * 60 * PRODUCTIVE_SHARE
                closing = date + timedelta(hours=17)
                while waiting and waiting[0]["created_at"] < closing:
                    minutes = max(0.3, rng.gauss(cfg["minutes"], cfg["minutes"] * 0.25))
                    if minutes > minutes_left:
                        break
                    minutes_left -= minutes
                    task = waiting.pop(0)
                    earliest = max(task["created_at"], date + timedelta(hours=8))
                    span = max(1, int((closing - earliest).total_seconds() // 60))
                    qa = ""
                    if rng.random() < QA_SAMPLE_RATE:
                        qa = "pass" if rng.random() < (0.80 if bad_qa else cfg["qa"]) else "fail"
                    task.update({
                        "completed_at": earliest + timedelta(minutes=rng.randint(1, span)),
                        "annotator_id": rng.choice(present), "handling_minutes": round(minutes, 2),
                        "qa_result": qa, "reworked": int(rng.random() < (0.12 if bad_qa else 0.05)),
                    })
                    tasks.append(task)
        for task in waiting:         # still open at the end of the period
            task.update({"completed_at": "", "annotator_id": "", "handling_minutes": "",
                         "qa_result": "", "reworked": 0})
            tasks.append(task)
    columns = ["task_id", "queue", "created_at", "due_at", "completed_at", "annotator_id",
               "handling_minutes", "qa_result", "reworked"]
    frame = pd.DataFrame(tasks)[columns].sort_values(["created_at", "task_id"])
    for col in ("created_at", "due_at", "completed_at"):
        frame[col] = frame[col].map(lambda v: v.strftime("%Y-%m-%d %H:%M") if v != "" else "")
    return frame.reset_index(drop=True), pd.DataFrame(workforce)
