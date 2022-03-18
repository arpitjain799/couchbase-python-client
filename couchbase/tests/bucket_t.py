import json
from uuid import uuid4

import pytest

from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.diagnostics import (EndpointPingReport,
                                   PingState,
                                   ServiceType)
from couchbase.exceptions import InvalidArgumentException
from couchbase.options import ClusterOptions, PingOptions
from couchbase.result import PingResult

from ._test_utils import TestEnvironment


class BucketDiagnosticsTests:

    @pytest.fixture(scope="class", name="cb_env")
    def couchbase_test_environment(self, couchbase_config):
        conn_string = couchbase_config.get_connection_string()
        username, pw = couchbase_config.get_username_and_pw()
        opts = ClusterOptions(PasswordAuthenticator(username, pw))
        cluster = Cluster(
            conn_string, opts)
        cluster.cluster_info()
        bucket = cluster.bucket(f"{couchbase_config.bucket_name}")

        coll = bucket.default_collection()
        cb_env = TestEnvironment(cluster, bucket, coll, couchbase_config, manage_buckets=True)

        yield cb_env
        cluster.close()

    @pytest.fixture(scope="class")
    def check_diagnostics_supported(self, cb_env):
        cb_env.check_if_feature_supported('diagnostics')

    @pytest.mark.usefixtures("check_diagnostics_supported")
    def test_ping(self, cb_env):
        bucket = cb_env.bucket
        result = bucket.ping()
        assert isinstance(result, PingResult)

        assert result.sdk is not None
        assert result.id is not None
        assert result.version is not None
        assert result.endpoints is not None
        for ping_reports in result.endpoints.values():
            for report in ping_reports:
                assert isinstance(report, EndpointPingReport)
                print(report)
                if report.state == PingState.OK:
                    assert report.id is not None
                    assert report.latency is not None
                    assert report.remote is not None
                    assert report.local is not None
                    assert report.service_type is not None

    @pytest.mark.usefixtures("check_diagnostics_supported")
    def test_ping_report_id(self, cb_env):
        bucket = cb_env.bucket
        report_id = uuid4()
        result = bucket.ping(PingOptions(report_id=report_id))
        assert str(report_id) == result.id

    @pytest.mark.usefixtures("check_diagnostics_supported")
    def test_ping_restrict_services(self, cb_env):
        bucket = cb_env.bucket
        services = [ServiceType.KeyValue]
        result = bucket.ping(PingOptions(service_types=services))
        keys = list(result.endpoints.keys())
        assert len(keys) == 1
        assert keys[0] == ServiceType.KeyValue

    @pytest.mark.usefixtures("check_diagnostics_supported")
    def test_ping_str_services(self, cb_env):
        bucket = cb_env.bucket
        services = [ServiceType.KeyValue.value, ServiceType.Query.value]
        result = bucket.ping(PingOptions(service_types=services))
        assert len(result.endpoints) >= 1

    @pytest.mark.usefixtures("check_diagnostics_supported")
    def test_ping_mixed_services(self, cb_env):
        bucket = cb_env.bucket
        services = [ServiceType.KeyValue, ServiceType.Query.value]
        result = bucket.ping(PingOptions(service_types=services))
        assert len(result.endpoints) >= 1

    @pytest.mark.usefixtures("check_diagnostics_supported")
    def test_ping_invalid_services(self, cb_env):
        bucket = cb_env.bucket
        with pytest.raises(InvalidArgumentException):
            bucket.ping(PingOptions(service_types=ServiceType.KeyValue))

    @pytest.mark.usefixtures("check_diagnostics_supported")
    def test_ping_as_json(self, cb_env):
        bucket = cb_env.bucket
        result = bucket.ping()
        assert isinstance(result, PingResult)
        result_str = result.as_json()
        assert isinstance(result_str, str)
        result_json = json.loads(result_str)
        assert result_json['version'] is not None
        assert result_json['id'] is not None
        assert result_json['sdk'] is not None
        assert result_json['services'] is not None
        for _, data in result_json['services'].items():
            if len(data):
                assert data[0]['id'] is not None
                assert data[0]['latency_us'] is not None
                assert data[0]['remote'] is not None
                assert data[0]['local'] is not None
                assert data[0]['state'] is not None
