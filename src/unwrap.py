# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: 2024, M.Heinze <matthias.heinze@iof.fraunhofer.de>, C.Munkelt <christoph.munkelt@iof.fraunhofer.de>
#
# SPDX-License-Identifier: BSD-3-Clause
#
# Distributed under the BSD-3-Clause License. See LICENSES for more information.
#
import os
import time

import cv2
import numpy as np

def bin_array(num, m):
    """Convert a positive integer num into an m-bit bit vector"""
    return np.array(list(np.binary_repr(num).zfill(m))).astype(np.int8)

def gray_code(n):
    """Conversion: decimal number, decimal equivalent of its gray code form"""
    return n ^ (n >> 1) # Right shift the number by 1 taking xor with original number

def inverse_gray_code(n):
    """Conversion: decimal number of gray code, its inverse in decimal form"""
    inv = 0
    while(n): # Taking xor until n becomes zero
        inv = inv ^ n
        n = n >> 1
    return inv

def unwrap(config, imagestack):

    gc_patterns_x, gc_patterns_y = \
        config["gc_patterns_x"],\
        config["gc_patterns_y"]
    sine_period_length_x, sine_period_length_y = \
        config["sine_period_length_x"],\
        config["sine_period_length_y"]
    sine_patterns_x, sine_patterns_y = \
        config["sine_patterns_x"],\
        config["sine_patterns_y"]

    patterns = np.asarray(imagestack).astype(np.float64)
    h, w = patterns.shape[-2:]

    avg = (patterns[0] + patterns[1]) / 2.0
    gc_x = (patterns[2:2 + gc_patterns_x] > avg).astype(np.int64)
    gc_y = (patterns[2 + gc_patterns_x + sine_patterns_x:2 + gc_patterns_x \
        + sine_patterns_x + gc_patterns_y] > avg).astype(np.int64)
    dec_x = np.full((h, w), np.nan)
    dec_y = np.full((h, w), np.nan)

    start_time = time.time()

    for y in range(h):
        for x in range(w):
            dec_x[y, x] = inverse_gray_code(int(''.join([str(i) for i in gc_x[:, y, x]]), 2))
            dec_y[y, x] = inverse_gray_code(int(''.join([str(i) for i in gc_y[:, y, x]]), 2))

    print("time for decode gray code {0:.2f} seconds".format( \
        time.time() - start_time))

    arctan_numerator_x   = np.zeros((h, w))
    arctan_denumerator_x = np.zeros((h, w))
    arctan_numerator_y   = np.zeros((h, w))
    arctan_denumerator_y = np.zeros((h, w))

    for i in range(sine_patterns_x):
        arctan_numerator_x = arctan_numerator_x + patterns[2+gc_patterns_x+i] \
            * np.sin(2*np.pi*i/sine_patterns_x)
        arctan_denumerator_x = arctan_denumerator_x+patterns[2+gc_patterns_x+i] \
            * np.cos(2*np.pi*i/sine_patterns_x)

    for i in range(sine_patterns_y):
        arctan_numerator_y = arctan_numerator_y + patterns[2+gc_patterns_x+sine_patterns_x+gc_patterns_y+i] \
            * np.sin(2*np.pi*i/sine_patterns_y)
        arctan_denumerator_y = arctan_denumerator_y + patterns[2+gc_patterns_x+sine_patterns_x+gc_patterns_y+i] \
            * np.cos(2*np.pi*i/sine_patterns_y)

    modulation_x = np.sqrt(arctan_numerator_x*arctan_numerator_x + arctan_denumerator_x*arctan_denumerator_x) / 8.0
    modulation_y = np.sqrt(arctan_numerator_y*arctan_numerator_y + arctan_denumerator_y*arctan_denumerator_y) / 8.0

    phi01_x = np.arctan2( arctan_numerator_x,  arctan_denumerator_x)
    phi02_x = np.arctan2(-arctan_numerator_x, -arctan_denumerator_x)
    phi01_y = np.arctan2( arctan_numerator_y,  arctan_denumerator_y)
    phi02_y = np.arctan2(-arctan_numerator_y, -arctan_denumerator_y)

    phi_mask_x = np.multiply((phi01_x >= -np.pi / 2), (phi01_x < np.pi / 2))
    phi_unwrapped_x             = phi02_x             + (dec_x             - np.mod(dec_x,             2) + 1) * np.pi
    phi_unwrapped_x[phi_mask_x] = phi01_x[phi_mask_x] + (dec_x[phi_mask_x] + np.mod(dec_x[phi_mask_x], 2)    ) * np.pi

    phi_mask_y = np.multiply((phi01_y >= -np.pi / 2), (phi01_y < np.pi / 2))
    phi_unwrapped_y             = phi02_y             + (dec_y             - np.mod(dec_y,             2) + 1) * np.pi
    phi_unwrapped_y[phi_mask_y] = phi01_y[phi_mask_y] + (dec_y[phi_mask_y] + np.mod(dec_y[phi_mask_y], 2)    ) * np.pi

    modulation_threshold = config["modulation_threshold"]
    print("modulation threshold is {:.0f}".format(modulation_threshold))
    phi_unwrapped_x[modulation_x<modulation_threshold] = np.nan
    phi_unwrapped_y[modulation_y<modulation_threshold] = np.nan

    print("time for unwrap {0:.2f} seconds".format( \
        time.time() - start_time))

    return (np.array([phi_unwrapped_x, phi_unwrapped_y]), \
            np.array([modulation_x, modulation_y]) )



def poly_coeffs(phase, degree):

    h, w = phase.shape[:2]
    xx, yy = np.mgrid[0:h, 0:w]

    point_cloud = np.zeros((h, w, 3))
    point_cloud[:, :, 0] = xx
    point_cloud[:, :, 1] = yy
    point_cloud[:, :, 2] = phase

    x = point_cloud[:, :, 0].flatten()
    y = point_cloud[:, :, 1].flatten()
    z = point_cloud[:, :, 2].flatten()
    
    x = x[np.isfinite(z)]
    y = y[np.isfinite(z)]
    z = z[np.isfinite(z)]

    M = [np.ones(x.shape)]
    for deg in range(1, degree+1):
        for y_deg in range(0, deg+1):
            M.append(np.power(x, deg-y_deg) * np.power(y, y_deg))

    M = np.asarray(M).T
    return np.linalg.solve(np.dot(M.T, M), np.dot(M.T, z))


def poly_dev(phase, poly_coeffs, degree):

    h, w = phase.shape[:2]
    xx, yy = np.mgrid[0:h, 0:w]

    point_cloud = np.zeros((h, w, 3))
    point_cloud[:, :, 0] = xx
    point_cloud[:, :, 1] = yy
    point_cloud[:, :, 2] = phase

    x = point_cloud[:, :, 0]
    y = point_cloud[:, :, 1]
    z = point_cloud[:, :, 2]
    
    z_fit = poly_coeffs[0]
    coeff_index = 1
    for deg in range(1, degree+1):
        for y_deg in range(0, deg+1):
            z_fit += poly_coeffs[coeff_index] * np.power(x, deg-y_deg) * np.power(y, y_deg)
            coeff_index += 1

    return z - z_fit



if __name__ == '__main__':

    print("np.__version__ {}", np.__version__)
    print("cv2.__version__ {}", cv2.__version__)
