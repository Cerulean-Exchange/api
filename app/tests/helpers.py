# -*- coding: utf-8 -*-

from falcon import testing

from app.app import app
from app import syncer

# Sync the initial data...
syncer.sync()


class AppTestCase(testing.TestCase):
    """Default app test-case."""

    def setUp(self):
        """Test setup."""
        super(AppTestCase, self).setUp()
        self.app = app
