"""Management command to view currently active transitions.

Usage:
    python manage.py autofixer_status
"""

from django.core.management.base import BaseCommand

from autofixer.tracker import Tracker


class Command(BaseCommand):
    help = 'Show currently active autofixer-tracked transitions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--chain', type=str, default=None,
            help='Show only transitions for the given root_id',
        )

    def handle(self, *args, **options):
        tracker = Tracker()

        if options['chain']:
            transitions = tracker.get_chain(options['chain'])
        else:
            transitions = tracker.get_active_transitions()

        if not transitions:
            self.stdout.write('No active transitions.')
            return

        self.stdout.write(f'Active transitions: {len(transitions)}\n')
        for at in transitions:
            dur = at.duration_seconds()
            dur_str = f'{dur:.1f}s' if dur else '?'
            self.stdout.write(
                f'  [{at.status:>9}] {at.process_class}.{at.action_name} '
                f'instance={at.instance_key} duration={dur_str} '
                f'tr_id={at.tr_id} root={at.root_id}'
            )
