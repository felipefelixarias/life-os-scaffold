#!/usr/bin/env python3
"""
Life-OS maintenance utilities.

Provides common maintenance tasks like cleaning up old data,
archiving completed items, and generating health reports.
"""

import csv
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import shutil

class MaintenanceManager:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.canonical_dir = self.data_dir / 'canonical'
        self.logs_dir = self.data_dir.parent / 'logs'
        self.archive_dir = Path('99-archive')

    def generate_health_report(self) -> Dict:
        """Generate a health report of the life-os system."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'files': {},
            'data_quality': {},
            'recommendations': []
        }

        # Check file health
        csv_files = [
            'tasks.csv', 'goals.csv', 'habits.csv', 'projects.csv',
            'calendar_events.csv', 'time_blocks.csv', 'time_logs.csv'
        ]

        for filename in csv_files:
            file_path = self.canonical_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        rows = list(reader)

                    report['files'][filename] = {
                        'exists': True,
                        'size_bytes': file_path.stat().st_size,
                        'row_count': len(rows) - 1,  # Exclude header
                        'last_modified': datetime.fromtimestamp(
                            file_path.stat().st_mtime
                        ).isoformat()
                    }
                except Exception as e:
                    report['files'][filename] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                report['files'][filename] = {'exists': False}

        # Analyze data quality
        report['data_quality'] = self._analyze_data_quality()

        # Generate recommendations
        report['recommendations'] = self._generate_recommendations(report)

        return report

    def _analyze_data_quality(self) -> Dict:
        """Analyze data quality metrics."""
        quality = {
            'task_health': {},
            'goal_progress': {},
            'habit_tracking': {}
        }

        # Task analysis
        tasks_file = self.canonical_dir / 'tasks.csv'
        if tasks_file.exists():
            try:
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    tasks = list(reader)

                total_tasks = len(tasks)
                completed_tasks = len([t for t in tasks if t.get('status') == 'completed'])
                blocked_tasks = len([t for t in tasks if t.get('status') == 'blocked'])
                overdue_tasks = 0

                today = datetime.now().date()
                for task in tasks:
                    if task.get('due_date'):
                        try:
                            due_date = datetime.strptime(task['due_date'], '%Y-%m-%d').date()
                            if due_date < today and task.get('status') not in ['completed', 'cancelled']:
                                overdue_tasks += 1
                        except ValueError:
                            pass

                quality['task_health'] = {
                    'total': total_tasks,
                    'completed': completed_tasks,
                    'blocked': blocked_tasks,
                    'overdue': overdue_tasks,
                    'completion_rate': completed_tasks / total_tasks if total_tasks > 0 else 0
                }
            except Exception as e:
                quality['task_health'] = {'error': str(e)}

        # Goal analysis
        goals_file = self.canonical_dir / 'goals.csv'
        if goals_file.exists():
            try:
                with open(goals_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    goals = list(reader)

                active_goals = len([g for g in goals if g.get('status') == 'active'])
                goals_with_metrics = len([g for g in goals if g.get('metric_target')])

                quality['goal_progress'] = {
                    'total': len(goals),
                    'active': active_goals,
                    'with_metrics': goals_with_metrics
                }
            except Exception as e:
                quality['goal_progress'] = {'error': str(e)}

        return quality

    def _generate_recommendations(self, report: Dict) -> List[str]:
        """Generate maintenance recommendations based on the report."""
        recommendations = []

        # Check for stale data
        for filename, info in report['files'].items():
            if info.get('exists') and info.get('last_modified'):
                modified = datetime.fromisoformat(info['last_modified'])
                days_old = (datetime.now() - modified).days

                if days_old > 30:
                    recommendations.append(
                        f"⚠️  {filename} hasn't been updated in {days_old} days"
                    )

        # Check task health
        task_health = report['data_quality'].get('task_health', {})
        if isinstance(task_health, dict):
            blocked = task_health.get('blocked', 0)
            overdue = task_health.get('overdue', 0)

            if blocked > 0:
                recommendations.append(f"🚧 {blocked} blocked tasks need attention")

            if overdue > 0:
                recommendations.append(f"⏰ {overdue} overdue tasks need review")

        # Check for empty files
        for filename, info in report['files'].items():
            if info.get('row_count') == 0:
                recommendations.append(f"📝 {filename} is empty - consider adding some data")

        if not recommendations:
            recommendations.append("✅ System is healthy!")

        return recommendations

    def archive_completed_items(self, days_old: int = 30) -> Dict:
        """Archive completed tasks and goals older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        archived = {'tasks': 0, 'goals': 0}

        # Archive completed tasks
        tasks_file = self.canonical_dir / 'tasks.csv'
        if tasks_file.exists():
            archived['tasks'] = self._archive_from_file(
                tasks_file, 'task', cutoff_date,
                lambda row: row.get('status') == 'completed'
            )

        # Archive completed goals
        goals_file = self.canonical_dir / 'goals.csv'
        if goals_file.exists():
            archived['goals'] = self._archive_from_file(
                goals_file, 'goal', cutoff_date,
                lambda row: row.get('status') == 'completed'
            )

        return archived

    def _archive_from_file(self, file_path: Path, item_type: str, cutoff_date: datetime,
                          should_archive_func) -> int:
        """Archive items from a CSV file based on criteria."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            to_archive = []
            to_keep = []

            for row in rows:
                if should_archive_func(row):
                    # Check if old enough to archive
                    last_updated = row.get('last_updated', '')
                    if last_updated:
                        try:
                            updated_date = datetime.strptime(last_updated, '%Y-%m-%d')
                            if updated_date < cutoff_date:
                                to_archive.append(row)
                            else:
                                to_keep.append(row)
                        except ValueError:
                            to_keep.append(row)  # Keep if can't parse date
                    else:
                        to_archive.append(row)  # Archive if no date
                else:
                    to_keep.append(row)

            if to_archive:
                # Write remaining items back
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    if to_keep:
                        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                        writer.writeheader()
                        writer.writerows(to_keep)

                # Write archived items to archive directory
                self.archive_dir.mkdir(exist_ok=True)
                archive_file = self.archive_dir / f"{datetime.now().strftime('%Y-%m-%d')}_{item_type}s.csv"

                with open(archive_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(to_archive)

                return len(to_archive)

        except Exception as e:
            print(f"Error archiving from {file_path}: {e}")
            return 0

        return 0

    def cleanup_logs(self, days_to_keep: int = 90) -> Dict:
        """Clean up old log entries."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cleaned = {'daily_log': 0, 'time_logs': 0}

        # Clean daily log
        daily_log = self.logs_dir / 'daily_log.csv'
        if daily_log.exists():
            cleaned['daily_log'] = self._cleanup_log_file(daily_log, cutoff_date, 'date')

        # Clean time logs
        time_logs = self.canonical_dir / 'time_logs.csv'
        if time_logs.exists():
            cleaned['time_logs'] = self._cleanup_log_file(time_logs, cutoff_date, 'date')

        return cleaned

    def _cleanup_log_file(self, file_path: Path, cutoff_date: datetime, date_column: str) -> int:
        """Remove old entries from a log file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            filtered_rows = []
            removed_count = 0

            for row in rows:
                entry_date_str = row.get(date_column, '')
                if entry_date_str:
                    try:
                        entry_date = datetime.strptime(entry_date_str, '%Y-%m-%d')
                        if entry_date >= cutoff_date:
                            filtered_rows.append(row)
                        else:
                            removed_count += 1
                    except ValueError:
                        filtered_rows.append(row)  # Keep if can't parse date
                else:
                    filtered_rows.append(row)

            # Write back filtered data
            if removed_count > 0:
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    if filtered_rows:
                        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                        writer.writeheader()
                        writer.writerows(filtered_rows)

            return removed_count

        except Exception as e:
            print(f"Error cleaning {file_path}: {e}")
            return 0

def main():
    """Main CLI interface for maintenance utilities."""
    if len(sys.argv) < 2:
        print("Usage: maintenance.py <command> [options]")
        print("Commands:")
        print("  health              Generate health report")
        print("  archive [days]      Archive completed items (default: 30 days)")
        print("  cleanup-logs [days] Clean old log entries (default: 90 days)")
        return

    command = sys.argv[1]

    # Default to the canonical data directory
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / 'data'

    manager = MaintenanceManager(str(data_dir))

    if command == 'health':
        report = manager.generate_health_report()

        print("🏥 Life-OS Health Report")
        print("=" * 50)
        print(f"Generated: {report['timestamp'][:19]}")
        print()

        print("📁 Files:")
        for filename, info in report['files'].items():
            if info.get('exists'):
                rows = info.get('row_count', 'unknown')
                size = info.get('size_bytes', 0) / 1024  # KB
                print(f"  ✅ {filename}: {rows} rows, {size:.1f} KB")
            else:
                print(f"  ❌ {filename}: missing")

        print("\n📊 Data Quality:")
        task_health = report['data_quality'].get('task_health', {})
        if isinstance(task_health, dict) and 'total' in task_health:
            print(f"  Tasks: {task_health['completed']}/{task_health['total']} completed "
                  f"({task_health['completion_rate']:.1%})")
            if task_health['overdue'] > 0:
                print(f"    ⚠️  {task_health['overdue']} overdue")
            if task_health['blocked'] > 0:
                print(f"    🚧 {task_health['blocked']} blocked")

        print("\n💡 Recommendations:")
        for rec in report['recommendations']:
            print(f"  {rec}")

    elif command == 'archive':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        archived = manager.archive_completed_items(days)

        total = sum(archived.values())
        if total > 0:
            print(f"📦 Archived {total} items older than {days} days:")
            for item_type, count in archived.items():
                if count > 0:
                    print(f"  {item_type}: {count}")
        else:
            print(f"📦 No items to archive (cutoff: {days} days)")

    elif command == 'cleanup-logs':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        cleaned = manager.cleanup_logs(days)

        total = sum(cleaned.values())
        if total > 0:
            print(f"🧹 Cleaned {total} old log entries (kept last {days} days):")
            for log_type, count in cleaned.items():
                if count > 0:
                    print(f"  {log_type}: {count}")
        else:
            print(f"🧹 No old log entries to clean (cutoff: {days} days)")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == '__main__':
    main()