import logging

import hlt
from hlt import Direction, Position, constants
from scipy.optimize import linear_sum_assignment
import numpy as np
from scheduling import calc_distances, target, index_to_cell, cell_to_index, best_path, Schedule
from matplotlib import pyplot as plt

returning_to_shipyard = set()


def returning(ship):
    return (ship.halite_amount > 0.75 * constants.MAX_HALITE) or (ship.id in returning_to_shipyard)


def mining(ship, local_halite):
    return (local_halite > 0.05 * constants.MAX_HALITE) or (0.2 * local_halite > ship.halite_amount)


def calc_shortest_dist(origin, destination):
    d_north, d_south, d_east, d_west = calc_distances(origin, destination)
    return min(d_north, d_south) + min(d_east, d_west)


def plot(costs, fn):
    """Plot a dictionary of costs"""
    fig, axes = plt.subplots(len(costs))
    for i, cost in enumerate(costs):
        im = axes[i].imshow(costs[cost])
        axes[i].set_title(cost)
        fig.colorbar(im, ax=axes[i])
        axes[i].xaxis.set_major_formatter(plt.NullFormatter())
        axes[i].yaxis.set_major_formatter(plt.NullFormatter())
    fig.savefig(fn, bbox_inches='tight')
    return


class Scheduler:
    """Keeps track of Assignments and translates them into a command list."""

    def __init__(self, _game_map, _me, ships, turnnumber):
        self.schedule = Schedule(_game_map)
        self.game_map = _game_map
        self.me = _me
        self.ships = ships
        self.turnnumber = turnnumber
        self.n = len(self.ships)  # Number of assignments/ships.
        self.m = self.game_map.width * self.game_map.height  # Number of cells/targets.

    def create_cost_matrix(self):
        """"Create a cost matrix for linear_sum_assignment() to determine the destination for each ship based on
        a combination of multiple costs matrices
        Note:
            The rows/columns of the cost matrix represent ships/targets. An
            element in the cost matrix represents the cost of moving a ship
            to a target. Some elements represent moves that are not possible
            in a single turn. However, because these have high costs, they will
            never be chosen by the algorithm.
        """

        cost_matrix = np.full((self.n, self.m), 9999)
        halite_matrix = self.halite_matrix()
        for i in range(len(self.ships)):
            dist_arr = self.schedule.dist_matrix[cell_to_index(self.ships[i])]
            cost_matrix[i][:] = (
                    np.max(np.sqrt(halite_matrix)) - np.sqrt(halite_matrix) +
                    dist_arr
            )
            if i == 0 and self.turnnumber in [2, 4, 6, 8]:
                plot(costs={
                    'cost_matrix': cost_matrix[0][:].reshape(32, 32),
                    'halite_matrix': (np.max(np.sqrt(halite_matrix)) - np.sqrt(halite_matrix)).reshape(32, 32),
                    'dist_arr': dist_arr.reshape(32, 32),
                }, fn=r'replays\img\ship_{}_turn_{}'.format(self.ships[0].id, self.turnnumber))
        return cost_matrix

    def halite_matrix(self):
        """ Create a 1D ndarray with halite"""
        halite_matrix = np.array(range(self.m))
        for j in halite_matrix:
            halite_matrix[j] = index_to_cell(j).halite_amount
        return halite_matrix

    def to_destination(self):
        """Find the fit for the cost matrix"""
        cost_matrix = self.create_cost_matrix()
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        for ship in self.ships:
            if ship.halite_amount < 0.25 * constants.MAX_HALITE:
                returning_to_shipyard.discard(ship.id)

        for i, j in zip(row_ind, col_ind):
            ship = self.ships[i]
            if returning(ship):
                returning_to_shipyard.add(ship.id)
                target = self.me.shipyard.position
            elif mining(ship, self.game_map[ship].halite_amount):
                target = ship.position
            else:
                target = index_to_cell(j).position
            self.schedule.assign(ship, target)
        return self.schedule
