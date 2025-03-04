"""
Tests for LinksCluster and LinksSubcluster classes.

LinksCluster original source:
https://github.com/QEDan/links_clustering/tree/master
"""
# pylint: disable=W0201, E1101

import numpy as np
import random

from links_cluster import LinksCluster, Cluster, Subcluster, CONVERSATION_TRESHOLD


class TestLinksCluster:
    """Tests for LinksCluster class."""
    def setup_method(self):
        """Setup for tests."""
        self.cluster_similarity_threshold = 0.3
        self.subcluster_similarity_threshold = 0.2
        self.pair_similarity_maximum = 1.0
        self.cluster = LinksCluster(self.cluster_similarity_threshold,
                                    self.subcluster_similarity_threshold,
                                    self.pair_similarity_maximum,
                                    store_vectors=True)
        self.vector_dim = 256

    def random_vec(self):
        """Generate random vector of the correct shape."""
        return np.random.random((self.vector_dim))

    def rotate_vec(self, vector, angle):
        """Rotate a vector in the x-y plane by angle (radians).

        Note that this only has the expected impact on the cosine
        similarity if the vector is mostly in the x-y plane.
        """
        rotation_matrix = np.identity(self.vector_dim)
        rotation_matrix[0:2, 0:2] = [
            [np.cos(angle), -1 * np.sin(angle)],
            [np.sin(angle), np.cos(angle)]]
        vector = rotation_matrix.dot(vector)
        return vector

    def test_init(self):
        """Test that cluster has the expected type."""
        assert isinstance(self.cluster, LinksCluster)

    def test_predict_once(self):
        """Test that first prediction returns None."""
        vector = np.random.random((self.vector_dim, ))
        prediction = self.cluster.predict(vector)
        assert prediction is None
        assert vector in self.cluster.get_all_vectors()

    def test_predict_many(self):
        """Test that we can make many predictions, multiple classes are predicted."""
        how_many = 100
        predictions = []
        vectors = []
        for _ in range(how_many):
            vector = np.random.uniform(0, 1, self.vector_dim)
            vector[0] += 1000.0
            if np.random.uniform(0, 1) < 0.5:
                vector = self.rotate_vec(vector, 3.14)
            prediction = self.cluster.predict(vector)
            vectors.append(vector)
            predictions.append(prediction)
        assert len(predictions) == how_many
        assert not all(p == 0 for p in predictions)
        assert len(vectors) == len(self.cluster.get_all_vectors())

    def test_add_same_subcluster(self):
        """Test clustering after adding within same subcluster."""
        vector = self.random_vec()
        vector[0] += 1000.0
        first_prediction = self.cluster.predict(vector)
        vector2 = self.rotate_vec(
            vector,
            0.1 * np.arccos(self.subcluster_similarity_threshold))
        second_prediction = self.cluster.predict(vector2)
        # assert first_prediction == second_prediction
        assert len(self.cluster.clusters) == 1
        assert len(self.cluster.clusters[0].subclusters) == 1  # Should be one subcluster

    def test_add_new_subcluster(self):
        """Test clustering after adding to new subcluster."""
        vector = self.random_vec()
        vector[0] += 1000.0
        first_prediction = self.cluster.predict(vector)
        vector2 = self.rotate_vec(
            vector,
            1.01 * np.arccos(self.subcluster_similarity_threshold))
        second_prediction = self.cluster.predict(vector2)
        # assert first_prediction == second_prediction
        assert len(self.cluster.clusters) == 1
        assert len(self.cluster.clusters[0].subclusters) == 2  # New subcluster created.

    def test_add_new_cluster(self):
        """Test clustering after adding to new subcluster."""
        vector = self.random_vec()
        vector[0] += 1000.0
        first_prediction = self.cluster.predict(vector)
        vector2 = self.rotate_vec(
            vector,
            2 * np.arccos(self.cluster_similarity_threshold))
        second_prediction = self.cluster.predict(vector2)
        assert first_prediction == None
        # assert second_prediction == 1
        assert len(self.cluster.clusters) == 2
        assert len(self.cluster.clusters[0].subclusters) == 1
        assert len(self.cluster.clusters[1].subclusters) == 1

    def test_add_edge(self):
        """Test adding an edge between subclusters."""
        sc1 = Subcluster(self.random_vec())
        sc2 = Subcluster(self.random_vec())
        self.cluster.add_edge(sc1, sc2)
        assert sc2 in sc1.connected_subclusters
        assert sc1 in sc2.connected_subclusters

    def test_update_edge_valid(self):
        """Test update_edge with a valid edge."""
        vector = self.random_vec()
        similar_vector = vector + 1.0e-6 * self.random_vec()
        sc1 = Subcluster(vector)
        sc2 = Subcluster(similar_vector)
        edge_is_valid = self.cluster.update_edge(sc1, sc2)
        assert edge_is_valid
        assert sc2 in sc1.connected_subclusters
        assert sc1 in sc2.connected_subclusters

    def test_update_edge_invalid(self):
        """Test update_edge with an invalid edge."""
        vector = self.random_vec()
        vector[0] += 1000.0
        different_vector = self.rotate_vec(vector, 3.14)
        sc1 = Subcluster(vector)
        sc2 = Subcluster(different_vector)
        self.cluster.add_edge(sc1, sc2)
        edge_is_valid = self.cluster.update_edge(sc1, sc2)
        assert not edge_is_valid
        assert sc2 not in sc1.connected_subclusters
        assert sc1 not in sc2.connected_subclusters

    def test_merge_subclusters(self):
        """Test that merging subclusters works as expected."""
        vector = self.random_vec()
        vector[0] += 1000.0
        first_prediction = self.cluster.predict(vector)
        vector2 = self.rotate_vec(
            vector,
            1.01 * np.arccos(self.subcluster_similarity_threshold))
        second_prediction = self.cluster.predict(vector2)
        # These asserts test that we have created 2 subclusters in the same cluster
        # assert first_prediction == second_prediction
        assert len(self.cluster.clusters) == 1
        assert len(self.cluster.clusters[0].subclusters) == 2

        # Edit current conversation times
        self.cluster.clusters[0].subclusters[0].current_conversation = {
            "start_time": 1,
            "end_time": 3,
            "duration": 2,
        }
        self.cluster.clusters[0].subclusters[1].current_conversation = {
            "start_time": 2,
            "end_time": 4,
            "duration": 2,
        }
        current_conversation_merged = {
            "start_time": 1,
            "end_time": 4,
            "duration": 3,
        }

        # Merge subclusters and test for correctness
        self.cluster.merge_subclusters(0, 0, 1)
        assert len(self.cluster.clusters) == 1
        assert len(self.cluster.clusters[0].subclusters) == 1
        assert self.cluster.clusters[0].subclusters[0].vector_count == 2
        assert len(self.cluster.clusters[0].subclusters[0].vectors) == 2
        np.testing.assert_array_almost_equal(
            self.cluster.clusters[0].subclusters[0].centroid,
            np.mean([vector, vector2], axis=0))
        
        # Test conversation times
        assert self.cluster.clusters[0].subclusters[0].current_conversation == current_conversation_merged

    def test_get_all_vectors(self):
        """Test that get_all_vectors returns all vectors."""
        how_many = 100
        for _ in range(how_many):
            vector = self.random_vec()
            self.cluster.predict(vector)
        assert how_many == len(self.cluster.get_all_vectors())

    def test_sim_threshold_limit(self):
        """Test that the limit for large k is near 1.0."""
        large_k = 2 ** 25
        thresh = self.cluster.sim_threshold(large_k, large_k)
        assert np.abs(thresh - 1.0) < 1.0e-6

    def test_calculate_time_info(self):
        """Test cluster calculate_time_info function"""
        vector = self.random_vec()
        vector[0] += 1000.0
        first_prediction = self.cluster.predict(vector)
        vector2 = self.rotate_vec(
            vector,
            1.01 * np.arccos(self.subcluster_similarity_threshold))
        second_prediction = self.cluster.predict(vector2)
        # assert first_prediction == second_prediction
        assert len(self.cluster.clusters) == 1
        assert len(self.cluster.clusters[0].subclusters) == 2  # New subcluster created.

        times = random.sample(range(30000), 400)
        times.sort()
        start_times = times[::4]
        start_times_2 = times[1::4]
        end_times = times[2::4]
        end_times_2 = times[3::4]

        assert len(start_times) == len(start_times_2) == len(end_times) == len(end_times_2)
        
        conversation_list = []
        conversation_list_2 = []
        conversation_list_merged = []
        for i in range(len(start_times)):
            conversation_list.append({
                "start_time": start_times[i],
                "end_time": end_times[i],
                "duration": end_times[i] - start_times[i],
            })
            conversation_list_2.append({
                "start_time": start_times_2[i],
                "end_time": end_times_2[i],
                "duration": end_times_2[i] - start_times_2[i],
            })
            conversation_list_merged.append({
                "start_time": start_times[i],
                "end_time": end_times_2[i],
                "duration": end_times_2[i] - start_times[i],
            })


        self.cluster.clusters[0].subclusters[0].conversations = conversation_list
        self.cluster.clusters[0].subclusters[1].conversations = conversation_list_2
        
        convs = self.cluster.clusters[0].calculate_conversation_list()
        convs_sorted = sorted(convs, key=lambda x: x["start_time"])
        assert convs != []
        assert convs == convs_sorted
        for i in range(1, len(convs)):
            assert convs[i]["start_time"] >= convs[i - 1]["end_time"] + CONVERSATION_TRESHOLD
    
    def test_merge_subclusters_times_overlapping(self):
        """
        Test that merging subclusters works as expected with 
        current conversations, that are overlapping.
        """
        vector = self.random_vec()
        vector[0] += 1000.0
        first_prediction = self.cluster.predict(vector)
        vector2 = self.rotate_vec(
            vector,
            1.01 * np.arccos(self.subcluster_similarity_threshold))
        second_prediction = self.cluster.predict(vector2)
        # These asserts test that we have created 2 subclusters in the same cluster
        # assert first_prediction == second_prediction
        assert len(self.cluster.clusters) == 1
        assert len(self.cluster.clusters[0].subclusters) == 2

        # Edit current conversation times
        self.cluster.clusters[0].subclusters[0].current_conversation = {
            "start_time": 1,
            "end_time": 3,
            "duration": 2,
        }
        self.cluster.clusters[0].subclusters[1].current_conversation = {
            "start_time": 2,
            "end_time": 4,
            "duration": 2,
        }
        current_conversation_merged = {
            "start_time": 1,
            "end_time": 4,
            "duration": 3,
        }

        # Merge subclusters and test for correctness
        self.cluster.merge_subclusters(0, 0, 1)
        assert len(self.cluster.clusters) == 1
        assert len(self.cluster.clusters[0].subclusters) == 1
        assert self.cluster.clusters[0].subclusters[0].vector_count == 2
        assert len(self.cluster.clusters[0].subclusters[0].vectors) == 2
        np.testing.assert_array_almost_equal(
            self.cluster.clusters[0].subclusters[0].centroid,
            np.mean([vector, vector2], axis=0))
        
        # Test conversation times
        assert self.cluster.clusters[0].subclusters[0].current_conversation == current_conversation_merged
        
    def test_merge_subclusters_times_non_overlapping(self):
        """
        Test that merging subclusters works as expected with 
        current conversations, that are not overlapping.
        """
        vector = self.random_vec()
        vector[0] += 1000.0
        first_prediction = self.cluster.predict(vector)
        vector2 = self.rotate_vec(
            vector,
            1.01 * np.arccos(self.subcluster_similarity_threshold))
        second_prediction = self.cluster.predict(vector2)
        # These asserts test that we have created 2 subclusters in the same cluster
        # assert first_prediction == second_prediction
        assert len(self.cluster.clusters) == 1
        assert len(self.cluster.clusters[0].subclusters) == 2

        # Edit current conversation times
        self.cluster.clusters[0].subclusters[0].current_conversation = {
            "start_time": 1,
            "end_time": 3,
            "duration": 2,
        }
        self.cluster.clusters[0].subclusters[1].current_conversation = {
            "start_time": 200,
            "end_time": 400,
            "duration": 200,
        }
        conversations = [{
            "start_time": 1,
            "end_time": 3,
            "duration": 2,
        }]
        current_conversation_merged = {
            "start_time": 200,
            "end_time": 400,
            "duration": 200,
        }

        # Merge subclusters and test for correctness
        self.cluster.merge_subclusters(0, 0, 1)
        assert len(self.cluster.clusters) == 1
        assert len(self.cluster.clusters[0].subclusters) == 1
        assert self.cluster.clusters[0].subclusters[0].vector_count == 2
        assert len(self.cluster.clusters[0].subclusters[0].vectors) == 2
        np.testing.assert_array_almost_equal(
            self.cluster.clusters[0].subclusters[0].centroid,
            np.mean([vector, vector2], axis=0))
        
        # Test conversation times
        assert self.cluster.clusters[0].subclusters[0].current_conversation == current_conversation_merged
        assert self.cluster.clusters[0].subclusters[0].conversations == conversations


class TestSubcluster:
    """Tests for Subcluster class."""
    def setup_method(self):
        """Setup for tests."""
        self.vector_dim = 256
        self.initial_vector = self.random_vec()
        self.subcluster = Subcluster(self.initial_vector, store_vectors=True)

    def random_vec(self):
        """Generate random vector of the correct shape."""
        return np.random.random((self.vector_dim))

    def test_init(self):
        """Test basic class initialization properties."""
        assert isinstance(self.subcluster, Subcluster)
        assert self.subcluster.vector_count == 1
        assert len(self.subcluster.vectors) == 1

    def test_store_vector(self):
        """Test that the input vectors are stored."""
        assert np.array_equal(self.initial_vector, self.subcluster.vectors[0])

    def test_add_vector(self):
        """Test that we can a new vector."""
        new_vector = self.random_vec()
        self.subcluster.add(new_vector)
        assert self.subcluster.vector_count == 2
        assert len(self.subcluster.vectors) == 2
        assert np.array_equal(self.subcluster.centroid,
                              np.mean([self.initial_vector, new_vector],
                                      axis=0))

    def test_add_multiple_vectors(self):
        """Test that we can add multiple vectors."""
        how_many = 10
        new_vectors = np.random.random((how_many, self.vector_dim))
        for i in range(how_many):
            new_vector = new_vectors[i]
            self.subcluster.add(new_vector)
        expected_centroid = np.mean(
            np.concatenate(
                [np.expand_dims(self.initial_vector, axis=0),
                 new_vectors],
                axis=0
            ),
            axis=0
        )
        assert self.subcluster.vector_count == how_many + 1
        assert len(self.subcluster.vectors) == how_many + 1
        np.testing.assert_array_almost_equal(
            self.subcluster.centroid,
            expected_centroid,
            decimal=12)

class TestCluster:
    def setup_method(self):
        """Setup for tests."""
        self.vector_dim = 256
        self.initial_vector = self.random_vec()
        subcluster = Subcluster(self.initial_vector, store_vectors=True)
        self.cluster = Cluster(subcluster)

    def random_vec(self):
        """Generate random vector of the correct shape."""
        return np.random.random((self.vector_dim))

    def test_init(self):
        """Test basic class initialization properties."""
        assert isinstance(self.cluster, Cluster)
        assert len(self.cluster.subclusters) == 1
        assert isinstance(self.cluster.subclusters[0], Subcluster)

    def test_merge_subclusters(self):
        """Test that subclusters can be merged."""
        new_vector = self.random_vec()
        new_subcluster = Subcluster(new_vector, store_vectors=True)
        self.cluster.add_subcluster(new_subcluster)

        self.cluster.subclusters[0].connected_subclusters.add(new_subcluster)
        new_subcluster.connected_subclusters.add(self.cluster.subclusters[0])

        assert len(self.cluster.subclusters) == 2
        assert self.cluster.subclusters[0].vector_count == 1
        assert len(self.cluster.subclusters[0].vectors) == 1
        assert self.cluster.subclusters[1].vector_count == 1
        assert len(self.cluster.subclusters[1].vectors) == 1

        self.cluster.merge_subclusters(0, 1)
        assert len(self.cluster.subclusters) == 1
        assert self.cluster.subclusters[0].vector_count == 2
        assert len(self.cluster.subclusters[0].vectors) == 2


    def test_merge_subclusters_connections(self):
        """Test that we can merge subclusters that have external edges."""
        new_vector_1 = self.random_vec()
        new_subcluster_1 = Subcluster(new_vector_1, store_vectors=True)
        self.cluster.add_subcluster(new_subcluster_1)
        new_vector_2 = self.random_vec()
        new_subcluster_2 = Subcluster(new_vector_2, store_vectors=True)
        self.cluster.add_subcluster(new_subcluster_2)

        new_subcluster_1.connected_subclusters.update(
            {new_subcluster_2, self.cluster.subclusters[0]})
        new_subcluster_2.connected_subclusters.update(
            {new_subcluster_1, self.cluster.subclusters[0]})
        self.cluster.subclusters[0].connected_subclusters.update(
            {new_subcluster_1, new_subcluster_2})
        
        self.cluster.merge_subclusters(0, 2)
        assert len(self.cluster.subclusters) == 2
        assert self.cluster.subclusters[0].vector_count == 2
        assert len(self.cluster.subclusters[0].vectors) == 2
        assert len(self.cluster.subclusters[0].connected_subclusters) == 1
        assert self.cluster.subclusters[0].connected_subclusters == {new_subcluster_1}
