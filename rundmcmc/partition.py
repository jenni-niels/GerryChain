import collections
import networkx

from rundmcmc.proposals import max_edge_cuts
from rundmcmc.updaters import flows_from_changes, compute_edge_flows


class Partition:
    """
    Partition represents a partition of the nodes of the graph. It will perform
    the first layer of computations at each step in the Markov chain - basic
    aggregations and calculations that we want to optimize.

    """

    def __init__(self, graph=None, assignment=None, updaters=None,
                 parent=None, flips=None):
        """
        :graph: Underlying graph; a NetworkX object.
        :assignment: Dictionary assigning nodes to districts. If None,
                     initialized to assign all nodes to district 0.
        :updaters: Dictionary of functions to track data about the partition.
                   The keys are stored as attributes on the partition class,
                   which the functions compute.

        """
        if parent:
            self._from_parent(parent, flips)
        else:
            self._first_time(graph, assignment, updaters)

        self._update()

        self.max_edge_cuts = max_edge_cuts(self)

    def _first_time(self, graph, assignment, updaters):
        self.graph = networkx.convert_node_labels_to_integers(
                                graph, label_attribute="OLDID")

        self.assignment = [0 for node in graph.nodes]

        if assignment:
            self.assignment = list(map(
                        networkx.get_node_attributes(
                            self.graph, assignment).get,
                            range(len(graph.nodes))
                        ))

        if not updaters:
            updaters = dict()

        self.updaters = updaters

        self.parent = None
        self.flips = None
        self.flows = None
        self.edge_flows = None

        self.max_edge_cuts = max_edge_cuts(self)

        self.parts = collections.defaultdict(set)
        for node, part in enumerate(self.assignment):
            self.parts[part].add(node)

    def _from_parent(self, parent, flips):
        self.parent = parent
        self.flips = flips

        self.assignment = [x for x in parent.assignment]
        for key, val in flips.items():
            self.assignment[key] = val

        self.graph = parent.graph
        self.updaters = parent.updaters

        self.max_edge_cuts = parent.max_edge_cuts

        self._update_parts()

    def __repr__(self):
        number_of_parts = len(self)
        s = "s" if number_of_parts > 1 else ""
        return f"Partition of a graph into {str(number_of_parts)} part{s}"

    def __len__(self):
        return len(self.parts)

    def _update_parts(self):
        self.flows = flows_from_changes(self.parent.assignment, self.flips)
        self.edge_flows = compute_edge_flows(self)

        # Parts must ontinue to be a defaultdict, so that new parts can appear.
        self.parts = collections.defaultdict(set, self.parent.parts)

        for part, flow in self.flows.items():
            self.parts[part] = (self.parent.parts[part] | flow['in']) - flow['out']

        # We do not want empty parts.
        self.parts = {part: nodes for part, nodes in self.parts.items() if len(nodes) > 0}

    def _update(self):
        self._cache = dict()

        for key in self.updaters:
            if key not in self._cache:
                self._cache[key] = self.updaters[key](self)

    def merge(self, flips):
        """
        :flips: dict assigning nodes of the graph to their new districts
        :returns: A new instance representing the partition obtained by performing the given flips
                  on this partition.

        """
        return self.__class__(parent=self, flips=flips)

    def crosses_parts(self, edge):
        return self.assignment[edge[0]] != self.assignment[edge[1]]

    def __getitem__(self, key):
        """Allows keying on a Partition instance.

        :key: Property to access.

        """
        if key not in self._cache:
            self._cache[key] = self.updaters[key](self)
        return self._cache[key]

    def assignment_by_nodeid(self):
        node_ids = list(map(
                    networkx.get_node_attributes(self.graph, "OLDID").get,
                    range(len(graph.nodes))))
        return dict(zip(node_ids, self.assignment))
