"""Usage summary calculation for par_cc_usage."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from .enums import TimeBucket
from .models import TimeBucketSummary, UnifiedBlock, UnifiedEntry, UsageSummaryData


class UsageSummaryCalculator:
    """Calculate usage summaries for different time buckets."""

    def __init__(self, timezone: str = "UTC"):
        """Initialize the calculator.

        Args:
            timezone: Timezone for bucket calculations
        """
        self.timezone = timezone

    async def calculate_summary(
        self,
        unified_entries: list[UnifiedEntry],
        unified_blocks: list[UnifiedBlock],
        time_bucket: TimeBucket,
        period_limit: int | None = None,
    ) -> UsageSummaryData:
        """Calculate usage summary for the specified time bucket.

        Args:
            unified_entries: List of unified entries from all projects/sessions
            unified_blocks: List of unified blocks
            time_bucket: Type of time bucketing to use
            period_limit: Limit to last N periods (optional)

        Returns:
            Complete usage summary data
        """
        summary = UsageSummaryData(time_bucket_type=time_bucket.value)

        if not unified_entries:
            return summary

        # Group entries by time bucket
        bucket_groups = self._group_entries_by_time_bucket(unified_entries, time_bucket, period_limit)

        # Calculate statistics for each bucket
        for period_name, (start_date, end_date, entries) in bucket_groups.items():
            bucket_summary = await self._calculate_bucket_statistics(
                period_name, start_date, end_date, entries, unified_blocks
            )
            summary.add_bucket(bucket_summary)

        # Calculate overall statistics
        summary.calculate_overall_averages()
        summary.calculate_overall_p90()

        # Update unique sets from entries
        for entry in unified_entries:
            summary.unique_projects.add(entry.project_name)
            summary.unique_sessions.add(entry.session_id)
            summary.unique_models.add(entry.model)
            summary.unique_tools.update(entry.tools_used)

        # Sort buckets by start date
        summary.buckets.sort(key=lambda b: b.start_date, reverse=True)

        return summary

    def _group_entries_by_time_bucket(
        self,
        entries: list[UnifiedEntry],
        time_bucket: TimeBucket,
        period_limit: int | None = None,
    ) -> dict[str, tuple[datetime, datetime, list[UnifiedEntry]]]:
        """Group entries by time bucket.

        Args:
            entries: List of unified entries
            time_bucket: Type of time bucketing
            period_limit: Limit to last N periods

        Returns:
            Dict mapping period names to (start_date, end_date, entries) tuples
        """
        if time_bucket == TimeBucket.ALL:
            if not entries:
                return {}

            sorted_entries = sorted(entries, key=lambda e: e.timestamp)
            start_date = sorted_entries[0].timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = sorted_entries[-1].timestamp.replace(hour=23, minute=59, second=59, microsecond=999999)

            return {"All Time": (start_date, end_date, entries)}

        bucket_groups: dict[str, list[UnifiedEntry]] = defaultdict(list)

        for entry in entries:
            period_name, start_date, end_date = self._get_period_info(entry.timestamp, time_bucket)
            bucket_groups[period_name].append(entry)

        # Apply period limit if specified
        if period_limit:
            # Sort by period name (which includes date) and take the most recent N periods
            sorted_periods = sorted(bucket_groups.keys(), reverse=True)
            limited_periods = sorted_periods[:period_limit]
            bucket_groups = {k: v for k, v in bucket_groups.items() if k in limited_periods}

        # Convert to final format with date boundaries
        result = {}
        for period_name, period_entries in bucket_groups.items():
            if period_entries:
                # Get period boundaries from first entry
                _, start_date, end_date = self._get_period_info(period_entries[0].timestamp, time_bucket)
                result[period_name] = (start_date, end_date, period_entries)

        return result

    def _get_period_info(self, timestamp: datetime, time_bucket: TimeBucket) -> tuple[str, datetime, datetime]:
        """Get period name and boundaries for a timestamp.

        Args:
            timestamp: The timestamp to categorize
            time_bucket: Type of time bucketing

        Returns:
            Tuple of (period_name, start_date, end_date)
        """
        if time_bucket == TimeBucket.DAILY:
            period_name = timestamp.strftime("%Y-%m-%d")
            start_date = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = timestamp.replace(hour=23, minute=59, second=59, microsecond=999999)

        elif time_bucket == TimeBucket.WEEKLY:
            # ISO week format (Monday = start of week)
            year, week, _ = timestamp.isocalendar()
            period_name = f"{year}-W{week:02d}"

            # Calculate Monday of that week
            days_since_monday = timestamp.weekday()
            monday = timestamp - timedelta(days=days_since_monday)
            start_date = monday.replace(hour=0, minute=0, second=0, microsecond=0)

            # Calculate Sunday of that week
            sunday = monday + timedelta(days=6)
            end_date = sunday.replace(hour=23, minute=59, second=59, microsecond=999999)

        elif time_bucket == TimeBucket.MONTHLY:
            period_name = timestamp.strftime("%Y-%m")
            start_date = timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Calculate last day of month
            if timestamp.month == 12:
                next_month = timestamp.replace(year=timestamp.year + 1, month=1, day=1)
            else:
                next_month = timestamp.replace(month=timestamp.month + 1, day=1)
            last_day = next_month - timedelta(days=1)
            end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=999999)

        else:
            raise ValueError(f"Unsupported time bucket: {time_bucket}")

        return period_name, start_date, end_date

    async def _calculate_bucket_statistics(
        self,
        period_name: str,
        start_date: datetime,
        end_date: datetime,
        entries: list[UnifiedEntry],
        unified_blocks: list[UnifiedBlock],
    ) -> TimeBucketSummary:
        """Calculate statistics for a single time bucket.

        Args:
            period_name: Name of the period
            start_date: Start of the time bucket
            end_date: End of the time bucket
            entries: Entries in this time bucket
            unified_blocks: All unified blocks for context

        Returns:
            Complete statistics for this time bucket
        """
        bucket = TimeBucketSummary(
            period_name=period_name,
            start_date=start_date,
            end_date=end_date,
        )

        if not entries:
            return bucket

        # Group entries by session and collect basic stats
        session_groups, projects, _models, _tools = self._group_entries_by_session(entries)

        # Calculate session-level statistics
        session_stats = await self._calculate_session_statistics(session_groups)

        # Update bucket with session totals and averages
        self._update_bucket_totals(bucket, session_stats)

        # Set activity statistics
        bucket.active_projects = len(projects)
        bucket.active_sessions = len(session_groups)

        # Count unified blocks that overlap with this time period
        bucket.unified_blocks_count = len(
            [b for b in unified_blocks if self._block_overlaps_period(b, start_date, end_date)]
        )

        # Calculate model and tool breakdowns
        await self._calculate_model_and_tool_breakdowns(bucket, entries)

        return bucket

    def _group_entries_by_session(
        self, entries: list[UnifiedEntry]
    ) -> tuple[dict[str, list[UnifiedEntry]], set[str], set[str], set[str]]:
        """Group entries by session and collect unique projects, models, and tools."""
        session_groups: dict[str, list[UnifiedEntry]] = defaultdict(list)
        projects = set()
        models = set()
        tools = set()

        for entry in entries:
            session_key = f"{entry.project_name}::{entry.session_id}"
            session_groups[session_key].append(entry)
            projects.add(entry.project_name)
            models.add(entry.model)
            tools.update(entry.tools_used)

        return session_groups, projects, models, tools

    async def _calculate_session_statistics(
        self, session_groups: dict[str, list[UnifiedEntry]]
    ) -> dict[str, int | float | list[int] | list[float]]:
        """Calculate per-session statistics for tokens, messages, and costs."""
        session_tokens: list[int] = []
        session_messages: list[int] = []
        session_costs: list[float] = []
        total_tokens = 0
        total_messages = 0
        total_cost = 0.0

        for session_entries in session_groups.values():
            session_token_total = sum(e.token_usage.total for e in session_entries)
            session_message_total = len(session_entries)
            session_cost_total = await self._calculate_session_cost(session_entries)

            session_tokens.append(session_token_total)
            session_messages.append(session_message_total)
            session_costs.append(session_cost_total)

            total_tokens += session_token_total
            total_messages += session_message_total
            total_cost += session_cost_total

        return {
            "session_tokens": session_tokens,
            "session_messages": session_messages,
            "session_costs": session_costs,
            "total_tokens": total_tokens,
            "total_messages": total_messages,
            "total_cost": total_cost,
        }

    async def _calculate_session_cost(self, session_entries: list[UnifiedEntry]) -> float:
        """Calculate total cost for a session."""
        session_cost_total = 0.0
        for entry in session_entries:
            try:
                from .pricing import calculate_token_cost

                usage = entry.token_usage
                cost_result = await calculate_token_cost(
                    entry.full_model_name,
                    usage.actual_input_tokens,
                    usage.actual_output_tokens,
                    usage.actual_cache_creation_input_tokens,
                    usage.actual_cache_read_input_tokens,
                )
                session_cost_total += cost_result.total_cost
            except Exception:
                # If cost calculation fails, continue without cost
                pass
        return session_cost_total

    def _update_bucket_totals(
        self, bucket: TimeBucketSummary, session_stats: dict[str, int | float | list[int] | list[float]]
    ) -> None:
        """Update bucket with totals, averages, and P90 values."""
        # Extract and cast the totals
        total_tokens = session_stats["total_tokens"]
        total_messages = session_stats["total_messages"]
        total_cost = session_stats["total_cost"]

        bucket.total_tokens = int(total_tokens) if isinstance(total_tokens, int | float) else 0
        bucket.total_messages = int(total_messages) if isinstance(total_messages, int | float) else 0
        bucket.total_cost = float(total_cost) if isinstance(total_cost, int | float) else 0.0

        # Extract the session lists
        session_tokens = session_stats["session_tokens"]
        session_messages = session_stats["session_messages"]
        session_costs = session_stats["session_costs"]

        # Ensure we have lists and calculate averages
        if isinstance(session_tokens, list) and len(session_tokens) > 0:
            session_count = len(session_tokens)
            bucket.average_tokens = bucket.total_tokens / session_count
            bucket.average_messages = bucket.total_messages / session_count
            bucket.average_cost = bucket.total_cost / session_count

            # Calculate P90 values with proper type casting
            if isinstance(session_tokens, list):
                int_tokens = [int(x) for x in session_tokens if isinstance(x, int | float)]
                bucket.p90_tokens = self._calculate_p90(int_tokens)
            if isinstance(session_messages, list):
                int_messages = [int(x) for x in session_messages if isinstance(x, int | float)]
                bucket.p90_messages = self._calculate_p90(int_messages)
            if isinstance(session_costs, list):
                float_costs = [float(x) for x in session_costs if isinstance(x, int | float)]
                bucket.p90_cost = self._calculate_p90_float(float_costs)

    async def _calculate_model_and_tool_breakdowns(
        self, bucket: TimeBucketSummary, entries: list[UnifiedEntry]
    ) -> None:
        """Calculate model and tool usage breakdowns."""
        for entry in entries:
            model = entry.model
            if model not in bucket.tokens_by_model:
                bucket.tokens_by_model[model] = 0
                bucket.messages_by_model[model] = 0
                bucket.cost_by_model[model] = 0.0

            bucket.tokens_by_model[model] += entry.token_usage.total
            bucket.messages_by_model[model] += 1

            # Calculate cost for this entry
            try:
                from .pricing import calculate_token_cost

                usage = entry.token_usage
                cost_result = await calculate_token_cost(
                    entry.full_model_name,
                    usage.actual_input_tokens,
                    usage.actual_output_tokens,
                    usage.actual_cache_creation_input_tokens,
                    usage.actual_cache_read_input_tokens,
                )
                bucket.cost_by_model[model] += cost_result.total_cost
            except Exception:
                pass

            # Tool usage
            bucket.total_tool_calls += entry.tool_use_count
            for tool in entry.tools_used:
                if tool not in bucket.tool_usage:
                    bucket.tool_usage[tool] = 0
                bucket.tool_usage[tool] += 1

    def _calculate_p90(self, values: list[int]) -> int:
        """Calculate P90 value for integer list."""
        if not values:
            return 0
        if len(values) == 1:
            return values[0]
        return int(statistics.quantiles(values, n=10)[8])

    def _calculate_p90_float(self, values: list[float]) -> float:
        """Calculate P90 value for float list."""
        if not values:
            return 0.0
        if len(values) == 1:
            return values[0]
        return statistics.quantiles(values, n=10)[8]

    def _block_overlaps_period(self, block: UnifiedBlock, start_date: datetime, end_date: datetime) -> bool:
        """Check if a unified block overlaps with the given time period."""
        block_end = block.actual_end_time or block.end_time
        return block.start_time <= end_date and block_end >= start_date
