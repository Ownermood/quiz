"""
MongoDB DatabaseManager for Telegram Quiz Bot
Owner ID: 8403136097
"""

import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.errors import PyMongoError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    logger.error("pymongo not installed. Run: pip install pymongo")


class DatabaseManager:
    def __init__(self, mongo_url: Optional[str] = None):
        if not PYMONGO_AVAILABLE:
            raise RuntimeError("pymongo is required. Run: pip install pymongo")

        url = mongo_url or os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("MONGODB_DB", "quiz_bot")

        self.client = MongoClient(url, serverSelectionTimeoutMS=10000)
        # Ping to verify connection
        self.client.admin.command('ping')
        self.db = self.client[db_name]

        self.questions_col  = self.db["questions"]
        self.users_col      = self.db["users"]
        self.groups_col     = self.db["groups"]
        self.broadcasts_col = self.db["broadcasts"]
        self.activities_col = self.db["activities"]
        self.developers_col = self.db["developers"]
        self.poll_map_col   = self.db["poll_map"]
        self.performance_col= self.db["performance"]

        self._ensure_indexes()
        logger.info(f"✅ MongoDB connected: {url} / db={db_name}")

    def _ensure_indexes(self):
        try:
            self.questions_col.create_index("id", unique=True)
            self.questions_col.create_index("category")
            self.users_col.create_index("user_id", unique=True)
            self.users_col.create_index([("last_seen", DESCENDING)])
            self.users_col.create_index([("total_answers", DESCENDING)])
            self.groups_col.create_index("chat_id", unique=True)
            self.groups_col.create_index([("last_active", DESCENDING)])
            self.poll_map_col.create_index("poll_id", unique=True)
            # Compound indexes for time-based activity queries (critical for leaderboards)
            self.activities_col.create_index([("type", ASCENDING), ("timestamp", DESCENDING)])
            self.activities_col.create_index([("type", ASCENDING), ("is_correct", ASCENDING), ("timestamp", DESCENDING)])
            self.activities_col.create_index([("type", ASCENDING), ("user_id", ASCENDING), ("timestamp", DESCENDING)])
            self.activities_col.create_index([("timestamp", DESCENDING)])
            self.performance_col.create_index([("metric", ASCENDING), ("timestamp", DESCENDING)])
            self.performance_col.create_index([("timestamp", DESCENDING)])
            self.broadcasts_col.create_index([("created_at", DESCENDING)])
        except Exception as e:
            logger.warning(f"Index creation warning: {e}")

    def _next_id(self, name: str) -> int:
        counter = self.db["_counters"].find_one_and_update(
            {"_id": name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True
        )
        return counter["seq"]

    # ── Questions ─────────────────────────────────────────────────────────────

    def get_all_questions(self) -> List[Dict]:
        docs = list(self.questions_col.find({}, {"_id": 0}))
        for d in docs:
            if isinstance(d.get("options"), str):
                import json
                try:
                    d["options"] = json.loads(d["options"])
                except Exception:
                    pass
        return docs

    def get_question_by_id(self, qid: int) -> Optional[Dict]:
        return self.questions_col.find_one({"id": qid}, {"_id": 0})

    def get_questions_by_category(self, category: str) -> List[Dict]:
        return list(self.questions_col.find({"category": category}, {"_id": 0}))

    def add_question(self, question: str, options: list, correct_answer: int,
                     category: str = "General") -> Optional[int]:
        """Add a question. Returns new DB id or None on failure."""
        try:
            new_id = self._next_id("questions")
            doc = {
                "id": new_id,
                "question": question,
                "options": options,
                "correct_answer": correct_answer,
                "category": category,
                "created_at": datetime.utcnow().isoformat()
            }
            self.questions_col.insert_one(doc)
            return new_id
        except Exception as e:
            logger.error(f"add_question error: {e}")
            return None

    def update_question(self, qid: int, question: str, options: list,
                        correct_answer: int) -> bool:
        try:
            result = self.questions_col.update_one(
                {"id": qid},
                {"$set": {"question": question, "options": options,
                           "correct_answer": correct_answer}}
            )
            return result.matched_count > 0
        except Exception as e:
            logger.error(f"update_question error: {e}")
            return False

    def delete_question(self, qid: int) -> bool:
        try:
            result = self.questions_col.delete_one({"id": qid})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"delete_question error: {e}")
            return False

    # ── Poll → Question mapping ───────────────────────────────────────────────

    def save_poll_mapping(self, poll_id: str, quiz_id: int):
        try:
            self.poll_map_col.update_one(
                {"poll_id": poll_id},
                {"$set": {"quiz_id": quiz_id}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"save_poll_mapping error: {e}")

    def get_quiz_id_from_poll(self, poll_id: str) -> Optional[int]:
        try:
            doc = self.poll_map_col.find_one({"poll_id": poll_id})
            return doc["quiz_id"] if doc else None
        except Exception:
            return None

    # ── Users ─────────────────────────────────────────────────────────────────

    def upsert_user(self, user_id: int, data: Dict):
        try:
            self.users_col.update_one(
                {"user_id": user_id},
                {"$set": data, "$setOnInsert": {"joined_at": datetime.utcnow().isoformat()}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"upsert_user error: {e}")

    def get_all_users_stats(self) -> List[Dict]:
        return list(self.users_col.find({}, {"_id": 0}))

    def get_active_users_count(self, days: int = 7) -> int:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        return self.users_col.count_documents({"last_seen": {"$gte": cutoff}})

    def get_new_users(self, days: int = 7) -> int:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        return self.users_col.count_documents({"joined_at": {"$gte": cutoff}})

    def get_most_active_users(self, limit: int = 10) -> List[Dict]:
        return list(self.users_col.find({}, {"_id": 0})
                    .sort("total_answers", DESCENDING).limit(limit))

    def get_pm_accessible_users(self) -> List[Dict]:
        return list(self.users_col.find({"pm_accessible": True}, {"_id": 0}))

    def remove_inactive_user(self, user_id: int) -> bool:
        result = self.users_col.delete_one({"user_id": user_id})
        return result.deleted_count > 0

    # ── Groups ────────────────────────────────────────────────────────────────

    def upsert_group(self, chat_id: int, data: Dict):
        try:
            self.groups_col.update_one(
                {"chat_id": chat_id},
                {"$set": data, "$setOnInsert": {"joined_at": datetime.utcnow().isoformat()}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"upsert_group error: {e}")

    def get_all_groups(self) -> List[Dict]:
        return list(self.groups_col.find({}, {"_id": 0}))

    def remove_inactive_group(self, chat_id: int) -> bool:
        result = self.groups_col.delete_one({"chat_id": chat_id})
        return result.deleted_count > 0

    # ── Developers ────────────────────────────────────────────────────────────

    def get_all_developers(self) -> List[Dict]:
        return list(self.developers_col.find({}, {"_id": 0}))

    def add_developer(self, user_id: int, username: str = "", name: str = "") -> bool:
        try:
            self.developers_col.update_one(
                {"user_id": user_id},
                {"$set": {"username": username, "name": name,
                           "added_at": datetime.utcnow().isoformat()}},
                upsert=True
            )
            return True
        except Exception:
            return False

    def remove_developer(self, user_id: int) -> bool:
        result = self.developers_col.delete_one({"user_id": user_id})
        return result.deleted_count > 0

    # ── Broadcasts ────────────────────────────────────────────────────────────

    def save_broadcast(self, data: Dict) -> int:
        new_id = self._next_id("broadcasts")
        data["id"] = new_id
        data.setdefault("created_at", datetime.utcnow().isoformat())
        self.broadcasts_col.insert_one(data)
        return new_id

    def log_broadcast(self, data: Dict):
        self.save_broadcast(data)

    def get_latest_broadcast(self) -> Optional[Dict]:
        return self.broadcasts_col.find_one({}, {"_id": 0},
                                             sort=[("created_at", DESCENDING)])

    def get_broadcast_by_id(self, bid: int) -> Optional[Dict]:
        return self.broadcasts_col.find_one({"id": bid}, {"_id": 0})

    def delete_broadcast(self, bid: int) -> bool:
        result = self.broadcasts_col.delete_one({"id": bid})
        return result.deleted_count > 0

    # ── Activities ────────────────────────────────────────────────────────────

    def log_activity(self, activity_type: str = None, data: Dict = None, **kwargs):
        """Flexible log_activity: accepts log_activity(type, dict) or log_activity(activity_type=x, key=val)."""
        doc = {"type": activity_type, "timestamp": datetime.utcnow().isoformat()}
        if data and isinstance(data, dict):
            doc.update(data)
        if kwargs:
            doc.update(kwargs)
        try:
            self.activities_col.insert_one(doc)
        except Exception as e:
            logger.error(f"log_activity error: {e}")

    def get_recent_activities(self, limit: int = 50) -> List[Dict]:
        return list(self.activities_col.find({}, {"_id": 0})
                    .sort("timestamp", DESCENDING).limit(limit))

    def get_activity_stats(self, days: int = 7) -> Dict:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        total = self.activities_col.count_documents({"timestamp": {"$gte": cutoff}})
        by_type = {}
        for row in self.activities_col.aggregate([
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$type", "count": {"$sum": 1}}}
        ]):
            by_type[row["_id"]] = row["count"]
        return {"total": total, "by_type": by_type}

    def get_user_engagement_stats(self) -> Dict:
        return {
            "total_users": self.users_col.count_documents({}),
            "active_7d": self.get_active_users_count(7),
            "active_30d": self.get_active_users_count(30)
        }

    def get_quiz_stats_by_period(self, days: int = 7) -> Dict:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        count = self.activities_col.count_documents(
            {"type": "quiz_answer", "timestamp": {"$gte": cutoff}})
        correct = self.activities_col.count_documents(
            {"type": "quiz_answer", "is_correct": True, "timestamp": {"$gte": cutoff}})
        return {"answers": count, "correct": correct, "period_days": days}

    # ── Performance ───────────────────────────────────────────────────────────

    def log_performance_metric(self, metric: str, value: float, extra: Dict = None):
        doc = {"metric": metric, "value": value,
               "timestamp": datetime.utcnow().isoformat(), **(extra or {})}
        self.performance_col.insert_one(doc)

    def get_performance_summary(self) -> Dict:
        result = {}
        for row in self.performance_col.aggregate([
            {"$group": {"_id": "$metric", "avg": {"$avg": "$value"}, "count": {"$sum": 1}}}
        ]):
            result[row["_id"]] = {"avg": row["avg"], "count": row["count"]}
        return result

    def get_response_time_trends(self, hours: int = 24) -> List[Dict]:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        return list(self.performance_col.find(
            {"metric": "response_time", "timestamp": {"$gte": cutoff}}, {"_id": 0}
        ).sort("timestamp", ASCENDING))

    def get_memory_usage_history(self, hours: int = 24) -> List[Dict]:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        return list(self.performance_col.find(
            {"metric": "memory", "timestamp": {"$gte": cutoff}}, {"_id": 0}
        ).sort("timestamp", ASCENDING))

    def get_error_rate_stats(self, hours: int = 24) -> Dict:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        errors = self.activities_col.count_documents(
            {"type": "error", "timestamp": {"$gte": cutoff}})
        total = self.activities_col.count_documents({"timestamp": {"$gte": cutoff}})
        return {"errors": errors, "total": total,
                "rate": (errors / total * 100) if total else 0}

    def get_api_call_counts(self, hours: int = 24) -> Dict:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        result = {}
        for row in self.activities_col.aggregate([
            {"$match": {"type": "api_call", "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$endpoint", "count": {"$sum": 1}}}
        ]):
            result[row["_id"]] = row["count"]
        return result

    def get_command_usage_stats(self, days: int = 7) -> Dict:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        result = {}
        for row in self.activities_col.aggregate([
            {"$match": {"type": "command", "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$command", "count": {"$sum": 1}}}
        ]):
            result[row["_id"]] = row["count"]
        return result

    # ── Metrics summary (used by /metrics endpoint) ───────────────────────────

    def get_metrics_summary(self) -> Dict:
        cutoff_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        cutoff_7d  = (datetime.utcnow() - timedelta(days=7)).isoformat()

        total_questions = self.questions_col.count_documents({})
        total_users     = self.users_col.count_documents({})
        total_groups    = self.groups_col.count_documents({})
        total_broadcasts= self.broadcasts_col.count_documents({})
        active_24h      = self.users_col.count_documents({"last_seen": {"$gte": cutoff_24h}})
        active_7d       = self.users_col.count_documents({"last_seen": {"$gte": cutoff_7d}})
        active_groups   = self.groups_col.count_documents({"last_active": {"$gte": cutoff_24h}})

        quiz_24h   = self.activities_col.count_documents(
            {"type": "quiz_answer", "timestamp": {"$gte": cutoff_24h}})
        correct_24h= self.activities_col.count_documents(
            {"type": "quiz_answer", "is_correct": True, "timestamp": {"$gte": cutoff_24h}})
        accuracy_24h = (correct_24h / quiz_24h * 100) if quiz_24h else 0

        commands_24h = self.activities_col.count_documents(
            {"type": "command", "timestamp": {"$gte": cutoff_24h}})
        errors_24h   = self.activities_col.count_documents(
            {"type": "error", "timestamp": {"$gte": cutoff_24h}})
        total_24h    = self.activities_col.count_documents({"timestamp": {"$gte": cutoff_24h}})
        error_rate   = (errors_24h / total_24h * 100) if total_24h else 0
        rate_limits  = self.activities_col.count_documents(
            {"type": "rate_limit", "timestamp": {"$gte": cutoff_24h}})

        # Average response time
        rt_docs = list(self.performance_col.find(
            {"metric": "response_time", "timestamp": {"$gte": cutoff_24h}}, {"value": 1}))
        avg_rt = (sum(d["value"] for d in rt_docs) / len(rt_docs)) if rt_docs else 0

        # Broadcast success rate
        bc_ok  = self.activities_col.count_documents(
            {"type": "broadcast_sent", "timestamp": {"$gte": cutoff_24h}})
        bc_fail= self.activities_col.count_documents(
            {"type": "broadcast_failed", "timestamp": {"$gte": cutoff_24h}})
        bc_total= bc_ok + bc_fail
        bc_rate = (bc_ok / bc_total * 100) if bc_total else 100

        return {
            "total_questions":       total_questions,
            "total_users":           total_users,
            "total_groups":          total_groups,
            "total_broadcasts":      total_broadcasts,
            "active_users_24h":      active_24h,
            "active_users_7d":       active_7d,
            "active_groups":         active_groups,
            "quiz_attempts_24h":     quiz_24h,
            "quiz_accuracy_24h":     round(accuracy_24h, 2),
            "commands_24h":          commands_24h,
            "error_rate_24h":        round(error_rate, 2),
            "rate_limit_violations_24h": rate_limits,
            "avg_response_time_24h": round(avg_rt, 2),
            "broadcast_success_rate": round(bc_rate, 2),
        }

    # ── Utility ───────────────────────────────────────────────────────────────


    def register_group_interaction(self, chat_id: int, thread_id=None,
                                    title: str = '', username: str = '') -> None:
        """Register/update a group when bot receives a command there.
        Stores message_thread_id so broadcast can respect forum topics."""
        data = {
            "chat_id":   chat_id,
            "title":     title,
            "username":  username,
            "last_active": datetime.utcnow().isoformat(),
        }
        if thread_id:
            data["message_thread_id"] = thread_id
        self.groups_col.update_one(
            {"chat_id": chat_id},
            {"$set": data, "$setOnInsert": {"joined_at": datetime.utcnow().isoformat()}},
            upsert=True
        )
    def format_relative_time(self, timestamp_str: str) -> str:
        try:
            ts = datetime.fromisoformat(timestamp_str)
            delta = datetime.utcnow() - ts
            if delta.days > 0:
                return f"{delta.days}d ago"
            elif delta.seconds >= 3600:
                return f"{delta.seconds // 3600}h ago"
            elif delta.seconds >= 60:
                return f"{delta.seconds // 60}m ago"
            else:
                return "just now"
        except Exception:
            return timestamp_str

    # ── Compatibility wrappers (for dev_commands.py legacy calls) ─────────────

    def get_quiz_stats_by_period(self, period) -> Dict:
        """Accept 'today','week','month','all' strings or int days."""
        mapping = {'today': 1, 'week': 7, 'month': 30, 'all': 36500}
        if isinstance(period, str):
            days = mapping.get(period, 7)
        else:
            days = int(period) if period else 7
        cutoff  = (datetime.utcnow() - timedelta(days=days)).isoformat()
        count   = self.activities_col.count_documents(
            {"type": "quiz_answer", "timestamp": {"$gte": cutoff}})
        correct = self.activities_col.count_documents(
            {"type": "quiz_answer", "is_correct": True, "timestamp": {"$gte": cutoff}})
        return {"answers": count, "correct": correct, "period_days": days,
                "total_quizzes": count, "correct_answers": correct}

    def get_performance_summary(self, hours=24) -> Dict:
        """Accept optional hours param."""
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        result = {}
        for row in self.performance_col.aggregate([
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$metric", "avg": {"$avg": "$value"}, "count": {"$sum": 1}}}
        ]):
            result[row["_id"]] = {"avg": row["avg"], "count": row["count"]}
        return result

    def get_activity_stats(self, days=7) -> Dict:
        """Accepts int days."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        total  = self.activities_col.count_documents({"timestamp": {"$gte": cutoff}})
        by_type = {}
        for row in self.activities_col.aggregate([
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$type", "count": {"$sum": 1}}}
        ]):
            by_type[row["_id"]] = row["count"]
        return {"total": total, "by_type": by_type}

    def get_error_rate_stats(self, hours=24) -> Dict:
        """Accept hours param."""
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        errors = self.activities_col.count_documents(
            {"type": "error", "timestamp": {"$gte": cutoff}})
        total  = self.activities_col.count_documents({"timestamp": {"$gte": cutoff}})
        return {"errors": errors, "total": total,
                "rate": (errors / total * 100) if total else 0}

    def get_command_usage_stats(self, days=7) -> Dict:
        """Accept days param."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        result = {}
        for row in self.activities_col.aggregate([
            {"$match": {"type": "command", "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$command", "count": {"$sum": 1}}}
        ]):
            result[row["_id"]] = row["count"]
        return result

    def add_developer(self, user_id: int, username: str = "", name: str = "",
                      added_by: int = None) -> bool:
        """Override to accept optional added_by param."""
        try:
            doc = {"username": username, "name": name,
                   "added_at": datetime.utcnow().isoformat()}
            if added_by:
                doc["added_by"] = added_by
            self.developers_col.update_one(
                {"user_id": user_id}, {"$set": doc}, upsert=True)
            return True
        except Exception as e:
            logger.error(f"add_developer error: {e}")
            return False

    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get a single user document by user_id."""
        try:
            return self.users_col.find_one({"user_id": user_id}, {"_id": 0})
        except Exception as e:
            logger.error(f"get_user error: {e}")
            return None

    def get_leaderboard_by_period(self, days: int, limit: int = 10) -> List[Dict]:
        """Return leaderboard of top users by correct answers in last N days."""
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            correct_agg = list(self.activities_col.aggregate([
                {"$match": {"type": "quiz_answer", "is_correct": True,
                            "timestamp": {"$gte": cutoff}}},
                {"$group": {"_id": "$user_id", "correct": {"$sum": 1}}}
            ]))
            total_agg = list(self.activities_col.aggregate([
                {"$match": {"type": "quiz_answer", "timestamp": {"$gte": cutoff}}},
                {"$group": {"_id": "$user_id", "total": {"$sum": 1}}}
            ]))
            correct_map = {r["_id"]: r["correct"] for r in correct_agg}
            total_map   = {r["_id"]: r["total"]   for r in total_agg}
            all_uids    = set(correct_map.keys()) | set(total_map.keys())
            entries = []
            for uid in all_uids:
                c = correct_map.get(uid, 0)
                t = total_map.get(uid, 0)
                acc = round(c / t * 100, 1) if t > 0 else 0
                entries.append({
                    "user_id":         uid,
                    "correct_answers": c,
                    "total_attempts":  t,
                    "accuracy":        acc,
                })
            entries.sort(key=lambda x: x["correct_answers"], reverse=True)
            return entries[:limit]
        except Exception as e:
            logger.error(f"get_leaderboard_by_period error: {e}")
            return []
