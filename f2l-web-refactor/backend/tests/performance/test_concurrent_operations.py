"""
Performance tests for concurrent operations.
"""
import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


@pytest.mark.performance
class TestConcurrentOperations:
    """Performance tests for concurrent operations."""

    @pytest.fixture
    def performance_test_client(self, test_client):
        """Test client configured for performance testing."""
        return test_client

    @pytest.fixture
    def sample_endpoints(self, performance_test_client):
        """Create sample endpoints for performance testing."""
        endpoints = []
        
        for i in range(5):
            endpoint_data = {
                'name': f'Performance Test Endpoint {i}',
                'endpoint_type': 'local',
                'base_path': f'/test/path/{i}',
                'is_active': True
            }
            
            response = performance_test_client.post("/api/v1/endpoints/", json=endpoint_data)
            assert response.status_code == 201
            endpoints.append(response.json())
        
        return endpoints

    @pytest.mark.slow
    def test_concurrent_endpoint_creation(self, performance_test_client):
        """Test concurrent endpoint creation performance."""
        def create_endpoint(index):
            endpoint_data = {
                'name': f'Concurrent Endpoint {index}',
                'endpoint_type': 'local',
                'base_path': f'/concurrent/path/{index}',
                'is_active': True
            }
            
            start_time = time.time()
            response = performance_test_client.post("/api/v1/endpoints/", json=endpoint_data)
            end_time = time.time()
            
            return {
                'index': index,
                'status_code': response.status_code,
                'duration': end_time - start_time,
                'success': response.status_code == 201
            }
        
        # Test with 20 concurrent endpoint creations
        num_concurrent = 20
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_endpoint, i) for i in range(num_concurrent)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Analyze results
        successful_requests = sum(1 for r in results if r['success'])
        average_duration = sum(r['duration'] for r in results) / len(results)
        max_duration = max(r['duration'] for r in results)
        min_duration = min(r['duration'] for r in results)
        
        # Performance assertions
        assert successful_requests == num_concurrent, "All requests should succeed"
        assert total_duration < 10.0, "Total time should be under 10 seconds"
        assert average_duration < 1.0, "Average request time should be under 1 second"
        assert max_duration < 2.0, "Max request time should be under 2 seconds"
        
        print(f"Concurrent endpoint creation performance:")
        print(f"  Total requests: {num_concurrent}")
        print(f"  Successful: {successful_requests}")
        print(f"  Total duration: {total_duration:.2f}s")
        print(f"  Average request time: {average_duration:.3f}s")
        print(f"  Min/Max request time: {min_duration:.3f}s / {max_duration:.3f}s")

    @pytest.mark.slow
    def test_concurrent_directory_browsing(self, performance_test_client, sample_endpoints):
        """Test concurrent directory browsing performance."""
        def browse_directory(endpoint_id, path_index):
            start_time = time.time()
            
            with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
                mock_manager = AsyncMock()
                # Simulate directory with many files
                mock_files = []
                for i in range(100):  # 100 files per directory
                    mock_files.append({
                        'name': f'file_{i:03d}.txt',
                        'path': f'/test/path/{path_index}/file_{i:03d}.txt',
                        'size': 1024 * (i + 1),
                        'modified_time': '2024-01-01T12:00:00Z',
                        'is_directory': False
                    })
                
                mock_manager.list_directory_recursive.return_value = mock_files
                mock_get_manager.return_value = mock_manager
                
                response = performance_test_client.get(
                    f"/api/v1/endpoints/{endpoint_id}/browse",
                    params={'path': f'/test/path/{path_index}', 'max_depth': 1}
                )
            
            end_time = time.time()
            
            return {
                'endpoint_id': endpoint_id,
                'path_index': path_index,
                'status_code': response.status_code,
                'duration': end_time - start_time,
                'file_count': len(response.json().get('items', [])) if response.status_code == 200 else 0,
                'success': response.status_code == 200
            }
        
        # Test concurrent browsing across multiple endpoints
        tasks = []
        for i, endpoint in enumerate(sample_endpoints):
            for path_idx in range(3):  # 3 paths per endpoint
                tasks.append((endpoint['id'], path_idx))
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(browse_directory, endpoint_id, path_idx) 
                      for endpoint_id, path_idx in tasks]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Analyze results
        successful_requests = sum(1 for r in results if r['success'])
        average_duration = sum(r['duration'] for r in results) / len(results)
        total_files_processed = sum(r['file_count'] for r in results)
        
        # Performance assertions
        assert successful_requests == len(tasks), "All browse requests should succeed"
        assert total_duration < 15.0, "Total browsing time should be under 15 seconds"
        assert average_duration < 2.0, "Average browse time should be under 2 seconds"
        
        print(f"Concurrent directory browsing performance:")
        print(f"  Total requests: {len(tasks)}")
        print(f"  Successful: {successful_requests}")
        print(f"  Total files processed: {total_files_processed}")
        print(f"  Total duration: {total_duration:.2f}s")
        print(f"  Average request time: {average_duration:.3f}s")

    @pytest.mark.slow
    def test_concurrent_sync_executions(self, performance_test_client, sample_endpoints):
        """Test concurrent sync execution performance."""
        # Create sync sessions
        sessions = []
        for i in range(3):  # 3 concurrent sync sessions
            session_data = {
                'name': f'Performance Sync Session {i}',
                'source_endpoint_id': sample_endpoints[i]['id'],
                'destination_endpoint_id': sample_endpoints[i + 1]['id'],
                'source_path': f'/source/{i}',
                'destination_path': f'/dest/{i}',
                'sync_direction': 'source_to_destination',
                'is_active': True
            }
            
            response = performance_test_client.post("/api/v1/sessions/", json=session_data)
            assert response.status_code == 201
            sessions.append(response.json())
        
        def execute_sync(session_id, session_index):
            start_time = time.time()
            
            with patch('app.api.v1.sessions.SyncService') as mock_sync_service:
                mock_service = AsyncMock()
                mock_sync_service.return_value = mock_service
                
                mock_execution = MagicMock()
                mock_execution.id = str(uuid4())
                mock_execution.status = 'running'
                mock_service.start_sync_execution.return_value = mock_execution
                
                response = performance_test_client.post(f"/api/v1/sessions/{session_id}/execute")
            
            end_time = time.time()
            
            return {
                'session_id': session_id,
                'session_index': session_index,
                'status_code': response.status_code,
                'duration': end_time - start_time,
                'execution_id': response.json().get('execution_id') if response.status_code == 202 else None,
                'success': response.status_code == 202
            }
        
        # Execute syncs concurrently
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(execute_sync, session['id'], i) 
                      for i, session in enumerate(sessions)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Analyze results
        successful_executions = sum(1 for r in results if r['success'])
        average_duration = sum(r['duration'] for r in results) / len(results)
        
        # Performance assertions
        assert successful_executions == len(sessions), "All sync executions should start successfully"
        assert total_duration < 5.0, "Total execution start time should be under 5 seconds"
        assert average_duration < 2.0, "Average execution start time should be under 2 seconds"
        
        print(f"Concurrent sync execution performance:")
        print(f"  Total executions: {len(sessions)}")
        print(f"  Successful starts: {successful_executions}")
        print(f"  Total duration: {total_duration:.2f}s")
        print(f"  Average start time: {average_duration:.3f}s")

    @pytest.mark.slow
    def test_api_response_times_under_load(self, performance_test_client, sample_endpoints):
        """Test API response times under load."""
        def make_api_request(request_type, endpoint_id=None):
            start_time = time.time()
            
            if request_type == 'list_endpoints':
                response = performance_test_client.get("/api/v1/endpoints/")
            elif request_type == 'get_endpoint' and endpoint_id:
                response = performance_test_client.get(f"/api/v1/endpoints/{endpoint_id}")
            elif request_type == 'health_check':
                with patch('app.api.v1.health.get_system_health') as mock_health:
                    mock_health.return_value = {
                        'overall_status': 'healthy',
                        'timestamp': '2024-01-01T12:00:00Z',
                        'health_checks': {},
                        'system_metrics': {},
                        'active_alerts': [],
                        'uptime_seconds': 86400
                    }
                    response = performance_test_client.get("/api/v1/health/")
            else:
                response = MagicMock()
                response.status_code = 404
            
            end_time = time.time()
            
            return {
                'request_type': request_type,
                'status_code': response.status_code,
                'duration': end_time - start_time,
                'success': response.status_code in [200, 201, 202]
            }
        
        # Create mixed load of different API requests
        requests = []
        for _ in range(10):  # 10 of each type
            requests.extend([
                ('list_endpoints', None),
                ('get_endpoint', sample_endpoints[0]['id']),
                ('health_check', None)
            ])
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_api_request, req_type, endpoint_id) 
                      for req_type, endpoint_id in requests]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Analyze results by request type
        by_type = {}
        for result in results:
            req_type = result['request_type']
            if req_type not in by_type:
                by_type[req_type] = []
            by_type[req_type].append(result)
        
        print(f"API response times under load:")
        print(f"  Total requests: {len(results)}")
        print(f"  Total duration: {total_duration:.2f}s")
        print(f"  Requests per second: {len(results) / total_duration:.1f}")
        
        for req_type, type_results in by_type.items():
            successful = sum(1 for r in type_results if r['success'])
            avg_duration = sum(r['duration'] for r in type_results) / len(type_results)
            max_duration = max(r['duration'] for r in type_results)
            
            print(f"  {req_type}:")
            print(f"    Successful: {successful}/{len(type_results)}")
            print(f"    Avg response time: {avg_duration:.3f}s")
            print(f"    Max response time: {max_duration:.3f}s")
            
            # Performance assertions per request type
            assert successful == len(type_results), f"All {req_type} requests should succeed"
            assert avg_duration < 1.0, f"Average {req_type} response time should be under 1 second"
            assert max_duration < 3.0, f"Max {req_type} response time should be under 3 seconds"

    @pytest.mark.slow
    def test_database_connection_pool_performance(self, performance_test_client):
        """Test database connection pool performance under load."""
        def database_intensive_request(request_index):
            start_time = time.time()
            
            # Make multiple database-intensive requests
            responses = []
            for i in range(5):  # 5 requests per thread
                response = performance_test_client.get("/api/v1/endpoints/")
                responses.append(response)
            
            end_time = time.time()
            
            return {
                'request_index': request_index,
                'duration': end_time - start_time,
                'requests_made': len(responses),
                'all_successful': all(r.status_code == 200 for r in responses)
            }
        
        # Test with high concurrency to stress connection pool
        num_threads = 25
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(database_intensive_request, i) 
                      for i in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Analyze results
        all_successful = all(r['all_successful'] for r in results)
        total_requests = sum(r['requests_made'] for r in results)
        average_thread_duration = sum(r['duration'] for r in results) / len(results)
        
        # Performance assertions
        assert all_successful, "All database requests should succeed"
        assert total_duration < 30.0, "Total test duration should be under 30 seconds"
        assert average_thread_duration < 10.0, "Average thread duration should be under 10 seconds"
        
        print(f"Database connection pool performance:")
        print(f"  Concurrent threads: {num_threads}")
        print(f"  Total requests: {total_requests}")
        print(f"  Total duration: {total_duration:.2f}s")
        print(f"  Requests per second: {total_requests / total_duration:.1f}")
        print(f"  Average thread duration: {average_thread_duration:.2f}s")
        print(f"  All requests successful: {all_successful}")

    @pytest.mark.slow
    def test_memory_usage_under_load(self, performance_test_client, sample_endpoints):
        """Test memory usage under sustained load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        def sustained_load_request(iteration):
            # Mix of different request types
            requests_per_iteration = 10
            for i in range(requests_per_iteration):
                if i % 3 == 0:
                    performance_test_client.get("/api/v1/endpoints/")
                elif i % 3 == 1:
                    endpoint_id = sample_endpoints[i % len(sample_endpoints)]['id']
                    performance_test_client.get(f"/api/v1/endpoints/{endpoint_id}")
                else:
                    with patch('app.api.v1.health.get_system_health') as mock_health:
                        mock_health.return_value = {
                            'overall_status': 'healthy',
                            'health_checks': {},
                            'system_metrics': {},
                            'active_alerts': []
                        }
                        performance_test_client.get("/api/v1/health/")
            
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            return {
                'iteration': iteration,
                'memory_mb': current_memory,
                'requests_made': requests_per_iteration
            }
        
        # Run sustained load for multiple iterations
        num_iterations = 20
        memory_samples = []
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(sustained_load_request, i) 
                      for i in range(num_iterations)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        total_requests = sum(r['requests_made'] for r in results)
        
        # Memory usage assertions
        assert memory_increase < 100, "Memory increase should be less than 100MB"
        assert final_memory < 500, "Final memory usage should be less than 500MB"
        
        print(f"Memory usage under sustained load:")
        print(f"  Initial memory: {initial_memory:.1f} MB")
        print(f"  Final memory: {final_memory:.1f} MB")
        print(f"  Memory increase: {memory_increase:.1f} MB")
        print(f"  Total requests: {total_requests}")
        print(f"  Total duration: {total_duration:.2f}s")
        print(f"  Memory per request: {memory_increase / total_requests * 1024:.1f} KB")

    @pytest.mark.slow
    def test_error_handling_under_load(self, performance_test_client):
        """Test error handling performance under load."""
        def make_error_request(error_type, request_index):
            start_time = time.time()
            
            if error_type == 'not_found':
                response = performance_test_client.get(f"/api/v1/endpoints/{uuid4()}")
                expected_status = 404
            elif error_type == 'validation_error':
                response = performance_test_client.post("/api/v1/endpoints/", json={
                    'name': '',  # Invalid empty name
                    'endpoint_type': 'invalid_type'
                })
                expected_status = 422
            elif error_type == 'method_not_allowed':
                response = performance_test_client.patch("/api/v1/health/")
                expected_status = 405
            else:
                response = MagicMock()
                response.status_code = 500
                expected_status = 500
            
            end_time = time.time()
            
            return {
                'error_type': error_type,
                'request_index': request_index,
                'status_code': response.status_code,
                'expected_status': expected_status,
                'duration': end_time - start_time,
                'handled_correctly': response.status_code == expected_status
            }
        
        # Create mix of error scenarios
        error_requests = []
        for i in range(50):  # 50 error requests total
            error_type = ['not_found', 'validation_error', 'method_not_allowed'][i % 3]
            error_requests.append((error_type, i))
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_error_request, error_type, req_idx) 
                      for error_type, req_idx in error_requests]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Analyze error handling performance
        correctly_handled = sum(1 for r in results if r['handled_correctly'])
        average_duration = sum(r['duration'] for r in results) / len(results)
        max_duration = max(r['duration'] for r in results)
        
        # Performance assertions for error handling
        assert correctly_handled == len(results), "All errors should be handled correctly"
        assert total_duration < 10.0, "Total error handling time should be under 10 seconds"
        assert average_duration < 0.5, "Average error response time should be under 0.5 seconds"
        assert max_duration < 2.0, "Max error response time should be under 2 seconds"
        
        print(f"Error handling performance under load:")
        print(f"  Total error requests: {len(results)}")
        print(f"  Correctly handled: {correctly_handled}")
        print(f"  Total duration: {total_duration:.2f}s")
        print(f"  Average response time: {average_duration:.3f}s")
        print(f"  Max response time: {max_duration:.3f}s")
