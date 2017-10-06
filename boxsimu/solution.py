# -*- coding: utf-8 -*-
"""
Created on Thu Jun 17 2017 at 12:07UTC

@author: Mathias Aschwanden (mathias.aschwanden@gmail.com)

"""

import copy
import time as time_module
import numpy as np
import dill as pickle
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from attrdict import AttrDict

from . import box as bs_box
from . import validation as bs_validation
from . import descriptors as bs_descriptors
from . import entities as bs_entities
from . import errors as bs_errors 
from . import process as bs_process
from . import system as bs_system
from . import transport as bs_transport
from . import utils as bs_utils
from . import ur


class Solution:
    """Storage of a simulation's solution.
    
    An instance of Solution stores the outcome and additional 
    meta-information of the simulation.
    Additionaly, the Solution class offers various plotting functions to 
    visualize the result of the simulation
    
    Args:
        system (BoxModelSystem): System that is simulated.
        total_integration_time (pint.Quantity [T]): Total length of the simulation.
        dt (pint.Quantity [T]): Integration timestep. 
    
    Attributes:
        total_integration_time (pint.Quantity): Total length of the simulation.
        dt (pint.Quantity): Integration timestep. 
        time (list of pint.Quantity): List of all times at which the system
            was solved (at which a result is available).
        system (BoxModelSystem): System which is simulated. 
        time_units (pint.Units): Units of Quantities within the time attribute.
        time_magnitude (float): Magnitudes of Quantities within the time 
            attribute.
        ts (AttrDict of AttrDict): For every box, there 
            exists one AttrDict which contains time series of all its 
            quantities (Fluid mass, Variable mass...) and the box instance.
            
    """

    total_integration_time = bs_descriptors.PintQuantityDescriptor(
            'total_integration_time', ur.second)
    dt = bs_descriptors.PintQuantityDescriptor('dt', ur.second)

    def __init__(self, system, N_timesteps, dt):
        self.system = system
        self.N_timesteps = N_timesteps
        self.dt = 1 * dt
        self.dt = self.dt.to_base_units()
        self.total_integration_time = N_timesteps * dt
        self.time_array = np.linspace(0, self.total_integration_time.magnitude,
                num=self.N_timesteps)
        self.time_units = self.dt.units
        
        self.setup_solution_dataframe()
        
        self.default_figsize = [7,4]
        self.yaxis_log = False

    def setup_solution_dataframe(self):
        # Setup Dataframe for timeseries of quantities (masses, volumes..)
        quantities = ['mass', 'volume'] + self.system.variable_names 
        col_tuples = [(box, quant) for box in self.system.box_names
                                   for quant in quantities]
        index = pd.MultiIndex.from_tuples(col_tuples, 
                names=['Box', 'Quantity'])
        self.df = pd.DataFrame(index=index).T
        self.df.units = ur.kg
        self.df.index.name = 'Timestep'

        # Setup Dataframe for timeseries of rates (proecesses, flows..)
        col_tuples = []
        for box_name, box in self.system.boxes.items():
            for variable_name, variable in self.system.variables.items():
                col_tuples.append((box_name, variable_name, 'flow'))
                col_tuples.append((box_name, variable_name, 'flux'))
                col_tuples.append((box_name, variable_name, 'process'))
                col_tuples.append((box_name, variable_name, 'reaction'))
                # flows = self.system.flows
                # fluxes = self.system.fluxes
                # print('---------------')
                # print('box: {}; variable: {}'.format(box_name, variable_name))
                # for flow in bs_transport.Flow.get_all_from(box, flows):
                #     print(flow)
                #     print(flow.source_box, flow.target_box)
                #     col_tuples.append((box_name, variable_name, 'flow', 
                #         flow.name))
                # for flow in bs_transport.Flow.get_all_to(box, flows):
                #     print(flow)
                #     print(flow.source_box, flow.target_box)
                #     col_tuples.append((box_name, variable_name, 'flow', 
                #         flow.name))
                # for flux in bs_transport.Flux.get_all_from(box, fluxes):
                #     if flux.variable == variable:
                #         col_tuples.append((box_name, variable_name, 'flow', 
                #             flux.name))
                # for flux in bs_transport.Flux.get_all_to(box, fluxes):
                #     if flux.variable == variable:
                #         col_tuples.append((box_name, variable_name, 'flow', 
                #             flux.name))

                # for process in box.processes:
                #     if process.variable == variable:
                #         col_tuples.append((box_name, variable_name, 
                #             'process', process.name))
                # for reaction in box.reactions:
                #     if variable in reaction.variables:
                #         col_tuples.append((box_name, variable_name, 
                #             'reaction', reaction.name))

        index = pd.MultiIndex.from_tuples(col_tuples, 
                names=['Box', 'Variable', 'Mechanism'])
        self.df_rates = pd.DataFrame(index=index).sort_index().T
        self.df_rates.units = ur.kg/ur.second
        self.df_rates.index.name = 'Starting Timestep'

    def add_timestep(self, timestep):
        """Add a timestep to the solution.

        Args:
            timestep (Timestep): Instance of class Timestep.

        """
        pass

    # VISUALIZATION

    def plot_fluid_masses(self, boxes=None, figsize=None, yaxis_log=False):
        if not yaxis_log:
            yaxis_log = self.yaxis_log
        if not self.time_units:
            self.time_units = self.time[0].units
        if not self.time_magnitude:
            self.time_magnitude = [t.magnitude for t in self.time]
        if not figsize:
            figsize = self.default_figsize

        fig, ax = self._get_subplots(
                title='Fluid Masses',
                xlabel=self.time_units,
                ylabel='kg',
                figsize=figsize,
                yaxis_log=yaxis_log)

        for box_name, ts in self.ts.items():
            masses = self.ts[box_name]['mass']
            mass_magnitude = [mass.magnitude for mass in masses]
            ax.plot(self.time_magnitude, mass_magnitude,
                    label='Box {}'.format(ts.box.id))

        ax.legend()
        return fig, ax

    def plot_variable_mass_of_all_boxes(self, variable, figsize=None, 
            yaxis_log=False):
        if not yaxis_log:
            yaxis_log = self.yaxis_log
        if not self.time_units:
            self.time_units = self.time[0].units

        if not figsize:
            figsize = self.default_figsize

        fig, ax = self._get_subplots(
                title='Variable Mass of {}'.format(variable.name),
                xlabel=self.time_units,
                ylabel='kg',
                figsize=figsize,
                yaxis_log=yaxis_log)

        for box_name, box in self.system.boxes.items():
            masses = self.df.loc[:, (box_name, variable.name)]
            ax.plot(self.time_array, masses,
                    label='Box {}'.format(box_name))
        ax.legend()
        return fig, ax

    def plot_variable_concentration_in_boxes(self, variable, boxes=None,
            figsize=None, yaxis_log=False, volumetric=False, units=None):
        """Plot the timeseries of the variable concentration [kg/kg] in Boxes.

        Plot the time series of the variable concentration [kg/kg] in the 
        specified Boxes. If no Boxes are specified (default) all boxes of the
        system are used.

        """
        if not boxes:
            boxes = self.system.box_list
        box_names = [box.name for box in boxes]
        if not yaxis_log:
            yaxis_log = self.yaxis_log
        if not self.time_units:
            self.time_units = self.time[0].units
        if not self.time_magnitude:
            self.time_magnitude = [t.magnitude for t in self.time]
        if not figsize:
            figsize = self.default_figsize
        if not units:
            if volumetric:
                y_label_text = 'kg/m^3'
                units = ur.kg/ur.meter**3
            else:
                y_label_text = 'kg/kg'
                units = ur.dimensionless
        else:
            if bs_validation.is_density(units):
                volumetric = True
            elif bs_validation.is_dimless(units):
                volumetric = False
            else:
                raise bs_errors.WrongUnitsDimensionalityError('Parameter units '
                        'has incorrect dimensionality!')
            y_label_text = units.format_babel()

        fig, ax = self._get_subplots(
                title='Variable Concentration of {}'.format(variable.name),
                xlabel=self.time_units,
                ylabel=y_label_text,
                figsize=figsize,
                yaxis_log=yaxis_log)

        for box_name, ts in self.ts.items():
            if not box_name in box_names:
                continue # This Box was not intended to be plotted
            var_mass_units = self.ts[box_name][variable.name][0].units
            var_mass_ts = np.array([m.magnitude 
                for m in self.ts[box_name][variable.name]]) * var_mass_units
            if volumetric:
                box_volume_units = self.ts[box_name]['volume'][0].units
                box_volume_ts = np.array([v.magnitude for v 
                    in self.ts[box_name]['volume']]) * box_volume_units
                concentrations = var_mass_ts / box_volume_ts
            else:
                box = self.system.boxes[box_name]
                concentrations = var_mass_ts / box.mass
            concentrations.ito(units)
            ax.plot(self.time_magnitude, concentrations,
                    label='Box {}'.format(ts.box.name))

        ax.legend()
        return fig, ax

    def plot_all_variable_mass_of_box(self, box, figsize=None, 
            yaxis_log=None):
        if not yaxis_log:
            yaxis_log = self.yaxis_log
        if not self.time_units:
            self.time_units = self.time[0].units
        if not self.time_magnitude:
            self.time_magnitude = [t.magnitude for t in self.time]

        if not figsize:
            figsize = self.default_figsize

        if yaxis_log:
            yaxis_log = 'log'
        else:
            yaxis_log = None

        fig, ax = self._get_subplots(
                title='Total Variable Masses',
                xlabel=self.time_units,
                ylabel='kg',
                figsize=figsize,
                yaxis_scale=yaxis_log)

        var_mass = []
        for variable in self.system.variable_list:
            var_mass += self.ts[box.name][variable.name]
            mass_magnitude = [mass.magnitude for mass in var_mass]
            ax.plot(self.time_magnitude, mass_magnitude,
                    label='Variable {}'.format(variable.name))
        ax.legend()
        return fig, ax

    def plot_total_variable_masses(self, figsize=None, yaxis_log=None):
        if not yaxis_log:
            yaxis_log = self.yaxis_log
        if not self.time_units:
            self.time_units = self.time[0].units
        if not self.time_magnitude:
            self.time_magnitude = [t.magnitude for t in self.time]

        if not figsize:
            figsize = self.default_figsize

        if yaxis_log:
            yaxis_log = 'log'
        else:
            yaxis_log = None

        fig, ax = self._get_subplots(
                title='Total Variable Mass',
                xlabel=self.time_units,
                ylabel='kg',
                figsize=figsize,
                yaxis_scale=yaxis_log)

        for variable in self.system.variable_list:
            var_masses = np.zeros(len(self.time_magnitude))
            i = 0
            for box_name, ts in self.ts.items():
                vm = bs_utils.get_array_quantity_from_array_of_quantities(
                        self.ts[box_name][variable.name])
                var_masses += vm
                i += 1
            mass_magnitude = [mass.magnitude for mass in var_masses]
            ax.plot(self.time_magnitude, mass_magnitude,
                    label='Variable {}'.format(variable.name))

        ax.legend()
        return fig, ax

    def _get_subplots(self, title, xlabel, ylabel, figsize=[10,10], 
            yaxis_log=False):
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.2e'))
        if yaxis_log: 
            ax.set_yscale('log')
        return fig, ax


    # PICKLING
    def save(self, file_name):
        """Pickle instance and save to file_name."""
        with open(file_name, 'wb') as f:
            pickle.dump(self, f)

    @classmethod
    def load(self, file_name):
        """Load pickled instance from file_name."""
        with open(file_name, 'rb') as f:
            solution = pickle.load(f)
            if not isinstance(solution, Solution):
                raise ValueError(
                        'Loaded pickle object is not a Solution instance!')
        return solution


