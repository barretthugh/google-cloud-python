# Copyright 2016 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import unittest

from google.cloud._testing import _GAXBaseAPI


TABLE_NAME = 'citizens'
COLUMNS = ['email', 'first_name', 'last_name', 'age']
VALUES = [
    [u'phred@exammple.com', u'Phred', u'Phlyntstone', 32],
    [u'bharney@example.com', u'Bharney', u'Rhubble', 31],
]


class _BaseTest(unittest.TestCase):

    PROJECT_ID = 'project-id'
    INSTANCE_ID = 'instance-id'
    INSTANCE_NAME = 'projects/' + PROJECT_ID + '/instances/' + INSTANCE_ID
    DATABASE_ID = 'database-id'
    DATABASE_NAME = INSTANCE_NAME + '/databases/' + DATABASE_ID
    SESSION_ID = 'session-id'
    SESSION_NAME = DATABASE_NAME + '/sessions/' + SESSION_ID

    def _make_one(self, *args, **kwargs):
        return self._getTargetClass()(*args, **kwargs)


class Test_BatchBase(_BaseTest):

    def _getTargetClass(self):
        from google.cloud.spanner.batch import _BatchBase

        return _BatchBase

    def _compare_values(self, result, source):
        from google.protobuf.struct_pb2 import ListValue
        from google.protobuf.struct_pb2 import Value

        for found, expected in zip(result, source):
            self.assertIsInstance(found, ListValue)
            self.assertEqual(len(found.values), len(expected))
            for found_cell, expected_cell in zip(found.values, expected):
                self.assertIsInstance(found_cell, Value)
                if isinstance(expected_cell, int):
                    self.assertEqual(
                        int(found_cell.string_value), expected_cell)
                else:
                    self.assertEqual(found_cell.string_value, expected_cell)

    def test_ctor(self):
        session = _Session()
        base = self._make_one(session)
        self.assertTrue(base._session is session)
        self.assertEqual(len(base._mutations), 0)

    def test__check_state_virtual(self):
        session = _Session()
        base = self._make_one(session)
        with self.assertRaises(NotImplementedError):
            base._check_state()

    def test_insert(self):
        from google.cloud.proto.spanner.v1.mutation_pb2 import Mutation

        session = _Session()
        base = self._make_one(session)

        base.insert(TABLE_NAME, columns=COLUMNS, values=VALUES)

        self.assertEqual(len(base._mutations), 1)
        mutation = base._mutations[0]
        self.assertIsInstance(mutation, Mutation)
        write = mutation.insert
        self.assertIsInstance(write, Mutation.Write)
        self.assertEqual(write.table, TABLE_NAME)
        self.assertEqual(write.columns, COLUMNS)
        self._compare_values(write.values, VALUES)

    def test_update(self):
        from google.cloud.proto.spanner.v1.mutation_pb2 import Mutation

        session = _Session()
        base = self._make_one(session)

        base.update(TABLE_NAME, columns=COLUMNS, values=VALUES)

        self.assertEqual(len(base._mutations), 1)
        mutation = base._mutations[0]
        self.assertIsInstance(mutation, Mutation)
        write = mutation.update
        self.assertIsInstance(write, Mutation.Write)
        self.assertEqual(write.table, TABLE_NAME)
        self.assertEqual(write.columns, COLUMNS)
        self._compare_values(write.values, VALUES)

    def test_insert_or_update(self):
        from google.cloud.proto.spanner.v1.mutation_pb2 import Mutation

        session = _Session()
        base = self._make_one(session)

        base.insert_or_update(TABLE_NAME, columns=COLUMNS, values=VALUES)

        self.assertEqual(len(base._mutations), 1)
        mutation = base._mutations[0]
        self.assertIsInstance(mutation, Mutation)
        write = mutation.insert_or_update
        self.assertIsInstance(write, Mutation.Write)
        self.assertEqual(write.table, TABLE_NAME)
        self.assertEqual(write.columns, COLUMNS)
        self._compare_values(write.values, VALUES)

    def test_replace(self):
        from google.cloud.proto.spanner.v1.mutation_pb2 import Mutation

        session = _Session()
        base = self._make_one(session)

        base.replace(TABLE_NAME, columns=COLUMNS, values=VALUES)

        self.assertEqual(len(base._mutations), 1)
        mutation = base._mutations[0]
        self.assertIsInstance(mutation, Mutation)
        write = mutation.replace
        self.assertIsInstance(write, Mutation.Write)
        self.assertEqual(write.table, TABLE_NAME)
        self.assertEqual(write.columns, COLUMNS)
        self._compare_values(write.values, VALUES)

    def test_delete(self):
        from google.cloud.proto.spanner.v1.mutation_pb2 import Mutation
        from google.cloud.spanner.keyset import KeySet

        keys = [[0], [1], [2]]
        keyset = KeySet(keys=keys)
        session = _Session()
        base = self._make_one(session)

        base.delete(TABLE_NAME, keyset=keyset)

        self.assertEqual(len(base._mutations), 1)
        mutation = base._mutations[0]
        self.assertIsInstance(mutation, Mutation)
        delete = mutation.delete
        self.assertIsInstance(delete, Mutation.Delete)
        self.assertEqual(delete.table, TABLE_NAME)
        key_set_pb = delete.key_set
        self.assertEqual(len(key_set_pb.ranges), 0)
        self.assertEqual(len(key_set_pb.keys), len(keys))
        for found, expected in zip(key_set_pb.keys, keys):
            self.assertEqual(
                [int(value.string_value) for value in found.values], expected)


class TestBatch(_BaseTest):

    def _getTargetClass(self):
        from google.cloud.spanner.batch import Batch

        return Batch

    def test_ctor(self):
        session = _Session()
        batch = self._make_one(session)
        self.assertTrue(batch._session is session)

    def test_commit_already_committed(self):
        from google.cloud.spanner.keyset import KeySet

        keys = [[0], [1], [2]]
        keyset = KeySet(keys=keys)
        database = _Database()
        session = _Session(database)
        batch = self._make_one(session)
        batch.committed = object()
        batch.delete(TABLE_NAME, keyset=keyset)

        with self.assertRaises(ValueError):
            batch.commit()

    def test_commit_grpc_error(self):
        from google.gax.errors import GaxError
        from google.cloud.proto.spanner.v1.transaction_pb2 import (
            TransactionOptions)
        from google.cloud.proto.spanner.v1.mutation_pb2 import (
            Mutation as MutationPB)
        from google.cloud.spanner.keyset import KeySet

        keys = [[0], [1], [2]]
        keyset = KeySet(keys=keys)
        database = _Database()
        api = database.spanner_api = _FauxSpannerAPI(
            _random_gax_error=True)
        session = _Session(database)
        batch = self._make_one(session)
        batch.delete(TABLE_NAME, keyset=keyset)

        with self.assertRaises(GaxError):
            batch.commit()

        (session, mutations, single_use_txn, options) = api._committed
        self.assertEqual(session, self.SESSION_NAME)
        self.assertTrue(len(mutations), 1)
        mutation = mutations[0]
        self.assertIsInstance(mutation, MutationPB)
        self.assertTrue(mutation.HasField('delete'))
        delete = mutation.delete
        self.assertEqual(delete.table, TABLE_NAME)
        keyset_pb = delete.key_set
        self.assertEqual(len(keyset_pb.ranges), 0)
        self.assertEqual(len(keyset_pb.keys), len(keys))
        for found, expected in zip(keyset_pb.keys, keys):
            self.assertEqual(
                [int(value.string_value) for value in found.values], expected)
        self.assertIsInstance(single_use_txn, TransactionOptions)
        self.assertTrue(single_use_txn.HasField('read_write'))
        self.assertEqual(options.kwargs['metadata'],
                         [('google-cloud-resource-prefix', database.name)])

    def test_commit_ok(self):
        import datetime
        from google.cloud.proto.spanner.v1.spanner_pb2 import CommitResponse
        from google.cloud.proto.spanner.v1.transaction_pb2 import (
            TransactionOptions)
        from google.cloud._helpers import UTC
        from google.cloud._helpers import _datetime_to_pb_timestamp

        now = datetime.datetime.utcnow().replace(tzinfo=UTC)
        now_pb = _datetime_to_pb_timestamp(now)
        response = CommitResponse(commit_timestamp=now_pb)
        database = _Database()
        api = database.spanner_api = _FauxSpannerAPI(
            _commit_response=response)
        session = _Session(database)
        batch = self._make_one(session)
        batch.insert(TABLE_NAME, COLUMNS, VALUES)

        committed = batch.commit()

        self.assertEqual(committed, now)
        self.assertEqual(batch.committed, committed)

        (session, mutations, single_use_txn, options) = api._committed
        self.assertEqual(session, self.SESSION_NAME)
        self.assertEqual(mutations, batch._mutations)
        self.assertIsInstance(single_use_txn, TransactionOptions)
        self.assertTrue(single_use_txn.HasField('read_write'))
        self.assertEqual(options.kwargs['metadata'],
                         [('google-cloud-resource-prefix', database.name)])

    def test_context_mgr_already_committed(self):
        import datetime
        from google.cloud._helpers import UTC

        now = datetime.datetime.utcnow().replace(tzinfo=UTC)
        database = _Database()
        api = database.spanner_api = _FauxSpannerAPI()
        session = _Session(database)
        batch = self._make_one(session)
        batch.committed = now

        with self.assertRaises(ValueError):
            with batch:
                pass  # pragma: NO COVER

        self.assertEqual(api._committed, None)

    def test_context_mgr_success(self):
        import datetime
        from google.cloud.proto.spanner.v1.spanner_pb2 import CommitResponse
        from google.cloud.proto.spanner.v1.transaction_pb2 import (
            TransactionOptions)
        from google.cloud._helpers import UTC
        from google.cloud._helpers import _datetime_to_pb_timestamp

        now = datetime.datetime.utcnow().replace(tzinfo=UTC)
        now_pb = _datetime_to_pb_timestamp(now)
        response = CommitResponse(commit_timestamp=now_pb)
        database = _Database()
        api = database.spanner_api = _FauxSpannerAPI(
            _commit_response=response)
        session = _Session(database)
        batch = self._make_one(session)

        with batch:
            batch.insert(TABLE_NAME, COLUMNS, VALUES)

        self.assertEqual(batch.committed, now)

        (session, mutations, single_use_txn, options) = api._committed
        self.assertEqual(session, self.SESSION_NAME)
        self.assertEqual(mutations, batch._mutations)
        self.assertIsInstance(single_use_txn, TransactionOptions)
        self.assertTrue(single_use_txn.HasField('read_write'))
        self.assertEqual(options.kwargs['metadata'],
                         [('google-cloud-resource-prefix', database.name)])

    def test_context_mgr_failure(self):
        import datetime
        from google.cloud.proto.spanner.v1.spanner_pb2 import CommitResponse
        from google.cloud._helpers import UTC
        from google.cloud._helpers import _datetime_to_pb_timestamp

        now = datetime.datetime.utcnow().replace(tzinfo=UTC)
        now_pb = _datetime_to_pb_timestamp(now)
        response = CommitResponse(commit_timestamp=now_pb)
        database = _Database()
        api = database.spanner_api = _FauxSpannerAPI(
            _commit_response=response)
        session = _Session(database)
        batch = self._make_one(session)

        class _BailOut(Exception):
            pass

        with self.assertRaises(_BailOut):
            with batch:
                batch.insert(TABLE_NAME, COLUMNS, VALUES)
                raise _BailOut()

        self.assertEqual(batch.committed, None)
        self.assertEqual(api._committed, None)
        self.assertEqual(len(batch._mutations), 1)


class _Session(object):

    def __init__(self, database=None, name=TestBatch.SESSION_NAME):
        self._database = database
        self.name = name


class _Database(object):
    name = 'testing'


class _FauxSpannerAPI(_GAXBaseAPI):

    _create_instance_conflict = False
    _instance_not_found = False
    _committed = None

    def commit(self, session, mutations,
               transaction_id='', single_use_transaction=None, options=None):
        from google.gax.errors import GaxError

        assert transaction_id == ''
        self._committed = (session, mutations, single_use_transaction, options)
        if self._random_gax_error:
            raise GaxError('error')
        return self._commit_response
