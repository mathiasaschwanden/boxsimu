# -*- coding: utf-8 -*-
"""
Created on Thu Jun 23 10:45:10 2016

@author: Mathias Aschwanden (mathias.aschwanden@gmail.com)

"""

import unittest
from unittest import TestCase

import sys
import copy
import pandas as pd
import numpy as np
import datetime
import math

from matplotlib import pyplot as plt

from pint import UnitRegistry
ur = UnitRegistry(autoconvert_offset_to_baseunit = True)

BOXSIMU_PATH = '/home/aschi/Documents/MyPrivateRepo/boxsimu_project'
if not BOXSIMU_PATH in sys.path:
    sys.path.append(BOXSIMU_PATH)

from boxsimu.entities import Fluid, Variable
from boxsimu.box import Box
from boxsimu.transport import  Flow, Flux
from boxsimu.condition import Condition
from boxsimu.system import BoxModelSystem 
from boxsimu.process import Process, Reaction
from boxsimu.solver import Solver
from boxsimu import utils
from boxsimu.simulations import boxmodelsystem3


class BoxModelSystem1Test(TestCase):
    """Test boxsimu framework using an intermediate complex box model."""

    def setUp(self, *args, **kwargs):
        self.system = boxmodelsystem3.get_system(ur)
        self.solver = Solver(self.system)
        self.box1 = self.system.boxes.box1

        self.A = self.system.variables.A
        self.B = self.system.variables.B
        self.C = self.system.variables.C
        self.D = self.system.variables.D

    def tearDown(self, *args, **kwargs):
       del(self.system)
       del(self.solver)
       del(self.box1)

       del(self.A)
       del(self.B)
       del(self.C)
       del(self.D)

    def assertPintQuantityAlmostEqual(self, q1, q2, rel_tol=1e-7):
        q1 = q1.to_base_units()
        q2 = q2.to_base_units()
        try:
            self.assertTrue(math.isclose(q1.magnitude, q2.magnitude, 
                rel_tol=rel_tol))
        except AssertionError:
            raise AssertionError(
                    '{} != {} with relative tolerance of {}'.format(
                            q1, q2, rel_tol 
                        )
            )
        self.assertEqual(q1.units, q2.units)

    #####################################################
    # Box Functions 
    #####################################################
    
    def test_mass(self):
        self.assertEqual(self.box1.mass, 1e5*ur.kg + 6*ur.kg)

    def test_volume(self):
        box1_context = self.system.get_box_context(self.box1)

        self.assertEqual(self.box1.get_volume(box1_context),
                1e5/1000 * ur.meter**3)

    def test_concentration(self):
        pass

    #####################################################
    # Base Functions 
    #####################################################
    
    def test_box_id(self):
        self.assertEqual(self.box1.id, 0)

    def test_variable_id(self):
        self.assertEqual(self.A.id, 0)
        self.assertEqual(self.B.id, 1)
        self.assertEqual(self.C.id, 2)
        self.assertEqual(self.D.id, 3)

    def test_N_boxes(self):
        self.assertEqual(self.system.N_boxes, 1)
    
    def test_N_variables(self):
        self.assertEqual(self.system.N_variables, 4)

    def test_context_of_box(self):
        global_context = self.system.get_box_context()
        box1_context = self.system.get_box_context(self.box1)
        
        # Test accessability of the condition attributes
        self.assertEqual(global_context.T, 295 * ur.kelvin)
        self.assertEqual(box1_context.T, 290 * ur.kelvin)

        # Test the accessability of the condition attributes of other boxes:
        self.assertEqual(global_context.box1.condition.T, 
                290 * ur.kelvin)
        self.assertEqual(global_context.global_condition.T, 
                295 * ur.kelvin) 

    def test_context_evaluation_lambda_func(self):
        global_context = self.system.get_box_context()
        box1_context = self.system.get_box_context(self.box1)

        lambda1 = lambda t, c: c.T / (100*ur.kelvin)
        self.assertEqual(lambda1(0*ur.second, global_context), 2.95)
        self.assertEqual(lambda1(0*ur.second, box1_context), 2.90)


    #####################################################
    # Fluid and Variable Mass/Concentration Vectors/Matrices
    #####################################################

    def test_fluid_mass_1Dlist_1Darray(self):
        m = self.system.get_fluid_mass_1Darray()
        self.assertEqual(m[self.box1.id], 1e5 * ur.kg)

    def test_variable_mass_1Darray(self):
        m = self.system.get_variable_mass_1Darray(self.A)
        self.assertEqual(m[self.box1.id], 3 * ur.kg)

        m = self.system.get_variable_mass_1Darray(self.B)
        self.assertEqual(m[self.box1.id], 3 * ur.kg)
        
        m = self.system.get_variable_mass_1Darray(self.C)
        self.assertEqual(m[self.box1.id], 0 * ur.kg)

        m = self.system.get_variable_mass_1Darray(self.D)
        self.assertEqual(m[self.box1.id], 0 * ur.kg)

    def test_variable_concentration_1Darray(self):
        def _c(var_mass, fluid_mass):
            return var_mass / (fluid_mass + var_mass) * ur.dimensionless

        c = self.system.get_variable_concentration_1Darray(self.A)
        self.assertAlmostEqual(c[self.box1.id], _c(3, 1e5))
        c = self.system.get_variable_concentration_1Darray(self.B)
        self.assertAlmostEqual(c[self.box1.id], _c(3, 1e5))
        c = self.system.get_variable_concentration_1Darray(self.C)
        self.assertAlmostEqual(c[self.box1.id], _c(0, 1e5))
        c = self.system.get_variable_concentration_1Darray(self.D)
        self.assertAlmostEqual(c[self.box1.id], _c(0, 1e5))

    #####################################################
    # Mass Flow Vectors/Matrices
    #####################################################

    def test_fluid_mass_internal_flow_2Darray(self):
        A = self.system.get_fluid_mass_internal_flow_2Darray(0*ur.second)
        # Check that diagonal elements are zero
        self.assertPintQuantityAlmostEqual(A[0, 0], 0*ur.kg/ur.year)

    def test_fluid_mass_flow_sink_1Darray(self):
        s = self.system.get_fluid_mass_flow_sink_1Darray(0*ur.second)
        self.assertPintQuantityAlmostEqual(s[self.box1.id], 1e3*ur.kg/ur.year)

    def test_fluid_mass_flow_source_1Darray(self):
        q = self.system.get_fluid_mass_flow_source_1Darray(0*ur.second)
        self.assertPintQuantityAlmostEqual(q[self.box1.id], 1e3*ur.kg/ur.year)

    #####################################################
    # Variable Sink/Source Vectors
    #####################################################

    def test_variable_internal_flow_2Darray(self):
        f_flow = np.ones(self.system.N_boxes)
        A = self.system.get_variable_internal_flow_2Darray(
                self.A, 0*ur.second, f_flow)
        self.assertEqual(A[0, 0], 0*ur.kg/ur.year)

        A = self.system.get_variable_internal_flow_2Darray(
                self.B, 0*ur.second, f_flow)
        self.assertEqual(A[0, 0], 0*ur.kg/ur.year)

        A = self.system.get_variable_internal_flow_2Darray(
                self.C, 0*ur.second, f_flow)
        self.assertEqual(A[0, 0], 0*ur.kg/ur.year)

        A = self.system.get_variable_internal_flow_2Darray(
                self.D, 0*ur.second, f_flow)
        self.assertEqual(A[0, 0], 0*ur.kg/ur.year)

    def test_variable_flow_sink_1Darray(self):
        f_flow = np.ones(self.system.N_boxes)

        s = self.system.get_variable_flow_sink_1Darray(self.A, 
                0*ur.second, f_flow)
        c = self.system.get_variable_concentration_1Darray(self.A)
        self.assertPintQuantityAlmostEqual(s[self.box1.id], 
                1e3 * ur.kg/ur.year * c[self.box1.id])

        s = self.system.get_variable_flow_sink_1Darray(self.B, 
                0*ur.second, f_flow)
        c = self.system.get_variable_concentration_1Darray(self.B)
        self.assertPintQuantityAlmostEqual(s[self.box1.id], 
                1e3 * ur.kg/ur.year * c[self.box1.id])

        s = self.system.get_variable_flow_sink_1Darray(self.C, 
                0*ur.second, f_flow)
        c = self.system.get_variable_concentration_1Darray(self.C)
        self.assertEqual(s[self.box1.id], 
                1e3 * ur.kg/ur.year * c[self.box1.id])

        s = self.system.get_variable_flow_sink_1Darray(self.C, 
                0*ur.second, f_flow)
        c = self.system.get_variable_concentration_1Darray(self.C)
        self.assertEqual(s[self.box1.id], 
                1e3 * ur.kg/ur.year * c[self.box1.id])

    def test_variable_flow_source_1Darray(self):
        box1_input_concentration = {self.A: 1*ur.gram/ur.kg,
                                  self.B: 2*ur.gram/ur.kg}

        q = self.system.get_variable_flow_source_1Darray(self.A, 0*ur.second)
        self.assertEqual(q[self.box1.id], 
                 1e3 * ur.kg/ur.year * box1_input_concentration[self.A])

        q = self.system.get_variable_flow_source_1Darray(self.B, 0*ur.second)
        self.assertEqual(q[self.box1.id], 
                 1e3 * ur.kg/ur.year * box1_input_concentration[self.B])

        q = self.system.get_variable_flow_source_1Darray(self.C, 0*ur.second)
        self.assertEqual(q[self.box1.id], 0 * ur.kg / ur.year)

        q = self.system.get_variable_flow_source_1Darray(self.D, 0*ur.second)
        self.assertEqual(q[self.box1.id], 0 * ur.kg / ur.year)

    def test_variable_process_sink_1Darray(self):
        s = self.system.get_variable_process_sink_1Darray(
                self.A, 0*ur.second)
        self.assertEqual(s[self.box1.id], 0*ur.kg/ur.year)

        s = self.system.get_variable_process_sink_1Darray(
                self.B, 0*ur.second)
        self.assertEqual(s[self.box1.id], 0*ur.kg/ur.year)

        s = self.system.get_variable_process_sink_1Darray(
                self.C, 0*ur.second)
        self.assertEqual(s[self.box1.id], 0*ur.kg/ur.year)

        s = self.system.get_variable_process_sink_1Darray(
                self.D, 0*ur.second)
        self.assertEqual(s[self.box1.id], 0*ur.kg/ur.year)

    def test_variable_process_source_1Darray(self):
        q = self.system.get_variable_process_source_1Darray(
                self.A, 0*ur.second)
        self.assertEqual(q[self.box1.id], 0*ur.kg/ur.year)

        q = self.system.get_variable_process_source_1Darray(
                self.B, 0*ur.second)
        self.assertEqual(q[self.box1.id], 0*ur.kg/ur.year)

        q = self.system.get_variable_process_source_1Darray(
                self.C, 0*ur.second)
        self.assertEqual(q[self.box1.id], 0*ur.kg/ur.year)

        q = self.system.get_variable_process_source_1Darray(
                self.D, 0*ur.second)
        self.assertEqual(q[self.box1.id], 0*ur.kg/ur.year)

    def test_variable_internal_flux_2Darray(self):
        A = self.system.get_variable_internal_flux_2Darray(
                self.A, 0*ur.second)
        self.assertEqual(A[0, 0], 0 * ur.kg / ur.year)

        A = self.system.get_variable_internal_flux_2Darray(
                self.B, 0*ur.second)
        self.assertEqual(A[0, 0], 0 * ur.kg / ur.year)

        A = self.system.get_variable_internal_flux_2Darray(
                self.C, 0*ur.second)
        self.assertEqual(A[0, 0], 0 * ur.kg / ur.year)

        A = self.system.get_variable_internal_flux_2Darray(
                self.D, 0*ur.second)
        self.assertEqual(A[0, 0], 0 * ur.kg / ur.year)

    def test_variable_flux_sink_1Darray(self):
        s = self.system.get_variable_flux_sink_1Darray(
                self.A, 0*ur.second)
        self.assertEqual(s[self.box1.id], 0 * ur.kg / ur.year)

        s = self.system.get_variable_flux_sink_1Darray(
                self.B, 0*ur.second)
        self.assertEqual(s[self.box1.id], 0 * ur.kg / ur.year)

        s = self.system.get_variable_flux_sink_1Darray(
                self.C, 0*ur.second)
        self.assertEqual(s[self.box1.id], 0 * ur.kg / ur.year)

        s = self.system.get_variable_flux_sink_1Darray(
                self.D, 0*ur.second)
        self.assertEqual(s[self.box1.id], 0 * ur.kg / ur.year)

    def test_variable_flux_source_1Darray(self):
        q = self.system.get_variable_flux_source_1Darray(
                self.A, 0*ur.second)
        self.assertEqual(q[self.box1.id], 0 * ur.kg / ur.year)

        q = self.system.get_variable_flux_source_1Darray(
                self.B, 0*ur.second)
        self.assertEqual(q[self.box1.id], 0 * ur.kg / ur.year)

        q = self.system.get_variable_flux_source_1Darray(
                self.C, 0*ur.second)
        self.assertEqual(q[self.box1.id], 0 * ur.kg / ur.year)

        q = self.system.get_variable_flux_source_1Darray(
                self.D, 0*ur.second)
        self.assertEqual(q[self.box1.id], 0 * ur.kg / ur.year)

#     def test_reaction_rate_cube(self):
#         C = self.system.get_reaction_rate_3Darray(
#                 0*ur.second)
#         m_no3 = self.system.get_variable_mass_1Darray(self.no3)
#         m_phyto = self.system.get_variable_mass_1Darray(self.phyto)
# 
#         rr_photosynthesis_la = 0.8 * m_no3[self.box1.id] / (7.0 * ur.year)
#         rr_photosynthesis_uo = 0.8 * m_no3[self.uo.id] / (7.0 * ur.year)
#         rr_remineralization_la = 0.4 * m_phyto[self.box1.id] / (114 * ur.year)
#         rr_remineralization_uo = 0.4 * m_phyto[self.uo.id] / (114 * ur.year)
#         rr_remineralization_do = 0.4 * m_phyto[self.do.id] / (114 * ur.year)
#         
#         # Lake photosynthesis
#         self.assertPintQuantityAlmostEqual(C[self.box1.id, self.po4.id, 0], 
#                 -rr_photosynthesis_la * 1)
#         self.assertPintQuantityAlmostEqual(C[self.box1.id, self.no3.id, 0], 
#                 -rr_photosynthesis_la * 7)
#         self.assertPintQuantityAlmostEqual(C[self.box1.id, self.phyto.id, 0], 
#                 rr_photosynthesis_la * 114)
# 
#         # Upper Ocean photosynthesis
#         self.assertPintQuantityAlmostEqual(C[self.uo.id, self.po4.id, 0], 
#                 -rr_photosynthesis_uo * 1)
#         self.assertPintQuantityAlmostEqual(C[self.uo.id, self.no3.id, 0], 
#                 -rr_photosynthesis_uo * 7)
#         self.assertPintQuantityAlmostEqual(C[self.uo.id, self.phyto.id, 0], 
#                 rr_photosynthesis_uo * 114)
# 
#         # Lake remineralization
#         self.assertPintQuantityAlmostEqual(C[self.box1.id, self.po4.id, 1], 
#                 rr_remineralization_la * 1)
#         self.assertPintQuantityAlmostEqual(C[self.box1.id, self.no3.id, 1], 
#                 rr_remineralization_la * 7)
#         self.assertPintQuantityAlmostEqual(C[self.box1.id, self.phyto.id, 1], 
#                 -rr_remineralization_la * 114)
# 
#         # Upper Ocean remineralization
#         self.assertPintQuantityAlmostEqual(C[self.uo.id, self.po4.id, 1], 
#                 rr_remineralization_uo * 1)
#         self.assertPintQuantityAlmostEqual(C[self.uo.id, self.no3.id, 1], 
#                 rr_remineralization_uo * 7)
#         self.assertPintQuantityAlmostEqual(C[self.uo.id, self.phyto.id, 1], 
#                 -rr_remineralization_uo * 114)
# 
#         # Deep Ocean remineralization; NOTE: the reaction-index is here 0 
#         # again, because the reactions are just filled in any order!
#         self.assertPintQuantityAlmostEqual(C[self.do.id, self.po4.id, 0], 
#                 rr_remineralization_do * 1)
#         self.assertPintQuantityAlmostEqual(C[self.do.id, self.no3.id, 0], 
#                 rr_remineralization_do * 7)
#         self.assertPintQuantityAlmostEqual(C[self.do.id, self.phyto.id, 0], 
#                 -rr_remineralization_do * 114)
# 
if __name__ == "__main__": 
    unittest.main()




