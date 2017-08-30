# cython: profile=True

import pdb
import copy
import time as time_module
import numpy as np
import matplotlib.pyplot as plt
from attrdict import AttrDict
import math

import solution as bs_solution
import utils as bs_utils
import dimensionality_validation as bs_dim_val
from . import ur


def solve_flows(system, total_integration_time, dt):
    print('Start solving the flows of the box model...')
    print('- total integration time: {}'.format(total_integration_time))
    print('- dt (time step): {}'.format(dt))

    # Get number of time steps - round up if there is a remainder
    N_timesteps = math.ceil(total_integration_time / dt)
    time = total_integration_time * 0

    # Start time of function
    start_time = time_module.time()

    sol = bs_solution.Solution(total_integration_time, dt, system)

    progress = 0
    for i in range(N_timesteps):
        # Calculate progress in percentage of processed timesteps
        progress_old = progress
        progress = round(float(i) / float(N_timesteps), 1) * 100.0
        if progress != progress_old:
            print("{}%".format(progress))
        sol.time.append(time)

        dm, f_flow = _calculate_mass_flows(system, time, dt)

        for box_name, box in system.boxes.items():
            # Write changes to box objects
            box.fluid.mass += dm[box.id]

            # Save to Solution instance
            sol.ts[box_name]['mass'].append(box.fluid.mass)

        time += dt

    # End Time of Function
    end_time = time_module.time()
    print('Function "solve_flows(...)" used {:3.3f}s'.format(
            end_time - start_time))
    return sol


def solve(system, total_integration_time, dt):
    print('Start solving the box model...')
    print('- total integration time: {}'.format(total_integration_time))
    print('- dt (time step): {}'.format(dt))

    if len(system.variable_list) == 0:
        return solve_flows(system, total_integration_time, dt)

    # Get number of time steps - round up if there is a remainder
    N_timesteps = math.ceil(total_integration_time / dt)
    time = total_integration_time * 0

    # Start time of function
    start_time = time_module.time()

    sol = bs_solution.Solution(total_integration_time, dt, system)

    progress = 0
    for i in range(N_timesteps):
        # Calculate progress in percentage of processed timesteps
        progress_old = progress
        progress = int(float(i) / float(N_timesteps)*10) * 10.0
        if progress != progress_old:
            print("{}%".format(progress))
        sol.time.append(time)
        print(i)

        ##################################################
        # Calculate Mass fluxes
        ##################################################

        dm, f_flow = _calculate_mass_flows(system, time, dt)

        ##################################################
        # Calculate Variable changes due to PROCESSES,
        # REACTIONS, FUXES and FLOWS
        ##################################################

        dvar = _calculate_changes_of_all_variables(system, 
                time, dt, f_flow)

        ##################################################
        # Apply changes to Boxes and save values to
        # Solution instance
        ##################################################

        for box in system.box_list:
            # Write changes to box objects
            box.fluid.mass += dm[box.id]

            # Save mass to Solution instance
            sol.ts[box.name]['mass'].append(box.fluid.mass)

            for variable in system.variable_list:
                var_name = variable.name
                system.boxes[box.name].variables[var_name].mass += \
                        dvar[box.id, variable.id]
                sol.ts[box.name][var_name].append(
                    system.boxes[box.name].variables[var_name].mass)
        time += dt

    # End Time of Function
    end_time = time_module.time()
    print(
        'Function "solve(...)" used {:3.3f}s'.format(
            end_time - start_time))
    return sol

# HELPER functions

def _calculate_mass_flows(system, time, dt):
    """Calculate mass changes of every box.

    Args:
        time (pint.Quantity [T]): Current time (age) of the system.
        dt (pint.Quantity [T]): Timestep used.

    Returns:
        dm (numpy 1D array of pint.Quantities): Mass changes of every box.
        f_flow (numpy 1D array): Reduction coefficient of the mass 
            flows (due to becoming-empty boxes -> box mass cannot 
            decrase below 0kg).

    """
    # f_flow is the reduction coefficent of the "sink-flows" of each box
    # scaling factor for sinks of each box
    f_flow = np.ones(system.N_boxes)
    v1 = np.ones(system.N_boxes)

    m_ini = system.get_fluid_mass_1Darray()

    # get internal flow matrix and calculate the internal souce and sink 
    # vectors. Also get the external sink and source vector
    A = system.get_fluid_mass_internal_flow_2Darray(time)
    # internal 
    s_i = bs_utils.dot(A, v1)
    q_i = bs_utils.dot(A.T, v1)
    s_e = system.get_fluid_mass_flow_sink_1Darray(time)
    q_e = system.get_fluid_mass_flow_source_1Darray(time)

    # calculate first estimate of mass change vector
    dm = (q_e + q_i - s_e - s_i) * dt
    # calculate first estimate of mass after timestep
    m = m_ini + dm

    while np.any(m.magnitude < 0):
        argmin = np.argmin(m)
        # Calculate net sink and source and mass of the 'empty' box.
        net_source = (q_e[argmin] + q_i[argmin])*dt
        net_sink = (s_e[argmin] + s_i[argmin])*dt
        available_mass = m_ini[argmin]
        total_mass = (net_source + available_mass).to_base_units()

        if total_mass.magnitude > 0: 
            f_new = (total_mass / net_sink).to_base_units().magnitude 
            f_flow[argmin] = min(f_new, f_flow[argmin] * 0.98)
        else:
            f_flow[argmin] = 0

        # Apply reduction of sinks of the box
        A = (A.T * f_flow).T
        s_i = bs_utils.dot(A, v1)
        q_i = bs_utils.dot(A.T, v1)
        s_e = f_flow * s_e
        dm = (q_e + q_i - s_e - s_i) * dt
        m = m_ini + dm
    return dm, f_flow

def _calculate_changes_of_all_variables(system, time, dt, f_flow):
    """ Calculates the changes of all variable in every box.

    Args:
        time (pint.Quantity [T]): Current time (age) of the system.
        dt (pint.Quantity [T]): Timestep used.
        f_flow (numpy 1D array): Reduction coefficient of the mass flows 
            due to empty boxes.

    Returns:
        dvar (numpy 2D array of pint.Quantities): Variables changes of 
            every box. First dimension are the boxes, second dimension
            are the variables.

    """
    # reduction coefficent of the "variable-sinks" of each box for the
    # treated variable
    # scaling factor for sinks of each box
    f_var = np.ones([system.N_boxes, system.N_variables])
    var_ini = bs_utils.stack([system.get_variable_mass_1Darray(
        variable) for variable in system.variable_list], axis=-1)

    while True:
        dvar_list = []
        net_sink_list = []
        net_source_list = []
        for variable in system.variable_list:       
            # Get variables sources (q) and sinks (s)
            # i=internal, e=external
            sink_flow, source_flow = _get_sink_source_flow(system, variable, 
                    time, dt, f_var, f_flow)
            sink_flux, source_flux = _get_sink_source_flux(system, variable, 
                    time, dt, f_var)
            sink_process, source_process = _get_sink_source_process(system, 
                    variable, time, dt, f_var)
            sink_reaction, source_reaction = _get_sink_source_reaction(system, 
                    variable, time, dt, f_var)

            net_sink = sink_flow + sink_flux + sink_process + sink_reaction
            net_source = (source_flow + source_flux + source_process + 
                    source_reaction)
            
            net_sink_list.append(net_sink.to_base_units())
            net_source_list.append(net_source.to_base_units())
            dvar_list.append((net_source - net_sink).to_base_units())
            
        dvar = bs_utils.stack(dvar_list, axis=-1)
        net_sink = bs_utils.stack(net_sink_list, axis=-1)
        net_source = bs_utils.stack(net_source_list, axis=-1)

        var = (var_ini + dvar).to_base_units()
        
        net_sink[net_sink.magnitude == 0] = np.nan  # to evade division by zero

        f_var_tmp = ((var_ini + net_source) / net_sink).magnitude 
        f_var_tmp[np.isnan(f_var_tmp)] = 1
        f_var_tmp[f_var_tmp > 1] = 1
        if np.any(f_var_tmp < 1):
            f_var_tmp[f_var_tmp < 1] -= 1e-15 # np.nextafter(0, 1)
            f_var *= f_var_tmp
        else:
            break
    return dvar

def _get_sink_source_flow(system, variable, time, dt, f_var, f_flow):
    v1 = np.ones(system.N_boxes)
    flows = system.flows
    A_flow = system.get_variable_internal_flow_2Darray(variable, 
            time, f_flow, flows)
    A_flow = (A_flow.T * f_var[:, variable.id]).T
    s_flow_i = bs_utils.dot(A_flow, v1)
    q_flow_i = bs_utils.dot(A_flow.T, v1)
    s_flow_e = system.get_variable_flow_sink_1Darray(variable, 
            time, f_flow, flows)
    s_flow_e = system.get_variable_flow_sink_1Darray(variable, 
            time, f_flow, flows) * f_var[:, variable.id]

    q_flow_e = system.get_variable_flow_source_1Darray(variable,
            time, flows)
    sink_flow = ((s_flow_i + s_flow_e) * dt).to_base_units()
    source_flow = ((q_flow_i + q_flow_e) * dt).to_base_units()
    return sink_flow, source_flow

def _get_sink_source_flux(system, variable, time, dt, f_var):
    v1 = np.ones(system.N_boxes)
    fluxes = system.fluxes
    A_flux = system.get_variable_internal_flux_2Darray(variable,
            time, fluxes)
    A_flux = (A_flux.T * f_var[:, variable.id]).T
    s_flux_i = bs_utils.dot(A_flux, v1)
    q_flux_i = bs_utils.dot(A_flux.T, v1)
    s_flux_e = system.get_variable_flux_sink_1Darray(variable, 
            time, fluxes)
    s_flux_e = system.get_variable_flux_sink_1Darray(variable, 
            time, fluxes) * f_var[:, variable.id]

    q_flux_e = system.get_variable_flux_source_1Darray(variable,
            time, fluxes)
    sink_flux = ((s_flux_i + s_flux_e) * dt).to_base_units()
    source_flux = ((q_flux_i + q_flux_e) * dt).to_base_units()
    dvar_flux = source_flux - sink_flux
    return sink_flux, source_flux

def _get_sink_source_process(system, variable, time, dt, f_var):
    processes = system.processes
    s_process = system.get_variable_process_sink_1Darray(variable, 
            time, processes)
    s_process = system.get_variable_process_sink_1Darray(variable, 
            time, processes) * f_var[:, variable.id]
    q_process = system.get_variable_process_source_1Darray(variable,
            time, processes)
    sink_process = (s_process * dt).to_base_units()
    source_process = (q_process * dt).to_base_units()
    return sink_process, source_process

def _get_sink_source_reaction(system, variable, time, dt, f_var):
    reactions = system.reactions
    rr_cube = system.get_reaction_rate_3Darray(time, reactions)

    ## APPLY CORRECTIONS HERE!
    if np.any(f_var < 1):
        f_rr_cube = np.ones_like(rr_cube)
        for index in np.argwhere(f_var < 1):
            reduction_factor = f_var[tuple(index)]
            box = system.box_list[index[0]]
            box_name = box.name
            variable_name = system.variable_list[index[1]].name
            sink_reaction_indecies = np.argwhere(rr_cube[index[0], index[1], :].magnitude < 0)
            sink_reaction_indecies = list(sink_reaction_indecies.flatten())

            for sink_reaction_index in sink_reaction_indecies:
                if f_rr_cube[index[0], index[1], sink_reaction_index] > reduction_factor:
                    f_rr_cube[index[0], :, sink_reaction_index] = reduction_factor
        rr_cube *= f_rr_cube


    # Set all positive values to 0
    sink_rr_cube = np.absolute(rr_cube.magnitude.clip(max=0)) * rr_cube.units
    # Set all negative values to 0
    source_rr_cube = rr_cube.magnitude.clip(min=0) * rr_cube.units
    s_reaction = sink_rr_cube.sum(axis=2)[:, variable.id]
    q_reaction = source_rr_cube.sum(axis=2)[:, variable.id]
    
    sink_reaction = (s_reaction * dt).to_base_units()
    source_reaction = (q_reaction * dt).to_base_units()
    return sink_reaction, source_reaction