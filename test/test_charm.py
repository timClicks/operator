#!/usr/bin/python3

import unittest
import tempfile
import shutil

from pathlib import Path

from juju.charm import CharmBase, CharmMeta
from juju.charm import CharmEvents
from juju.framework import Framework


class TestCharm(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

        class TestCharmEvents(CharmEvents):
            pass
        # Relations events are defined dynamically and modify the class attributes.
        # We use a subclass temporarily to prevent these side effects from leaking.
        CharmBase.on = TestCharmEvents()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

        CharmBase.on = CharmEvents()

    def create_framework(self):
        return Framework(self.tmpdir / "framework.data")

    def test_basic(self):

        class MyCharm(CharmBase):

            def __init__(self, framework, key, metadata):
                super().__init__(framework, key, metadata)

                self.started = False
                framework.observe(self.on.start, self)

            def on_start(self, event):
                self.started = True

        framework = self.create_framework()
        charm = MyCharm(framework, None, CharmMeta())
        charm.on.start.emit()

        self.assertEqual(charm.started, True)

    def test_relation_events(self):

        class MyCharm(CharmBase):
            def __init__(self, framework, key, metadata):
                super().__init__(framework, key, metadata)
                self.seen = []
                for event_kind, bound_event in self.on.events().items():
                    # hook up relation events to generic handler
                    if 'relation' in event_kind:
                        framework.observe(bound_event, self.on_any_relation)

            def on_any_relation(self, event):
                self.seen.append(f'{type(event).__name__}')

        metadata = CharmMeta({
            'name': 'my-charm',
            'requires': {
                'req1': {'interface': 'req1'},
                'req2': {'interface': 'req2'},
            },
            'provides': {
                'pro1': {'interface': 'pro1'},
                'pro2': {'interface': 'pro2'},
            },
            'peers': {
                'peer1': {'interface': 'peer1'},
            },
        })

        charm = MyCharm(self.create_framework(), None, metadata)

        charm.on.req1_relation_joined.emit()
        charm.on.req1_relation_changed.emit()
        charm.on.req2_relation_changed.emit()
        charm.on.pro1_relation_departed.emit()
        charm.on.peer1_relation_broken.emit()

        charm.on.relation['req1'].joined.emit()

        self.assertEqual(charm.seen, [
            'RelationJoinedEvent',
            'RelationChangedEvent',
            'RelationChangedEvent',
            'RelationDepartedEvent',
            'RelationBrokenEvent',
            'RelationJoinedEvent',
        ])

    def test_storage_events(self):

        class MyCharm(CharmBase):
            def __init__(self, framework, key, metadata):
                super().__init__(framework, key, metadata)
                self.seen = []
                framework.observe(self.on.stor1_storage_attached, self)
                framework.observe(self.on.stor2_storage_detaching, self)

            def on_stor1_storage_attached(self, event):
                self.seen.append(f'{type(event).__name__}')

            def on_stor2_storage_detaching(self, event):
                self.seen.append(f'{type(event).__name__}')

        metadata = CharmMeta({
            'name': 'my-charm',
            'storage': {
                'stor1': {'type': 'filesystem'},
                'stor2': {
                    'type': 'filesystem',
                    'multiple': {
                        'range': '2',
                    },
                },
                'stor3': {
                    'type': 'filesystem',
                    'multiple': {
                        'range': '2-',
                    },
                },
                'stor4': {
                    'type': 'filesystem',
                    'multiple': {
                        'range': '2-4',
                    },
                },
            },
        })

        self.assertIsNone(metadata.storage['stor1'].multiple_range)
        self.assertEqual(metadata.storage['stor2'].multiple_range, (2, 2))
        self.assertEqual(metadata.storage['stor3'].multiple_range, (2, None))
        self.assertEqual(metadata.storage['stor4'].multiple_range, (2, 4))

        charm = MyCharm(self.create_framework(), None, metadata)

        charm.on.stor1_storage_attached.emit()
        charm.on.stor2_storage_detaching.emit()

        charm.on.storage["stor1"].attached.emit()

        self.assertEqual(charm.seen, [
            'StorageAttachedEvent',
            'StorageDetachingEvent',
            'StorageAttachedEvent',
        ])


if __name__ == "__main__":
    unittest.main()
