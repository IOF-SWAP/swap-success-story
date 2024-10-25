# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: 2024, M.Heinze <matthias.heinze@iof.fraunhofer.de>, C.Munkelt <christoph.munkelt@iof.fraunhofer.de>
#
# SPDX-License-Identifier: BSD-3-Clause
#
# Distributed under the BSD-3-Clause License. See LICENSES for more information.
#
import os
import copy

import cv2
import numpy as np

import unwrap

def save_float_big(filename, arr):

    assert arr.ndim == 2
    assert arr.dtype == np.float32

    TYPE = { 'BYTE': 0x01, 'WORD': 0x02, 'DWORD': 0x04,
            'FLOAT': 0x14, 'DOUBLE': 0x18, 'COLOR': 0x23, 'FLOAT3': 0x0C }

    UNDEF = 3.402823466e38
    with open(filename, "wb") as f:
        buffer = copy.deepcopy(arr)
        buffer[np.isnan(buffer)] = UNDEF
        header = np.array([buffer.shape[1], buffer.shape[0], TYPE['FLOAT'], 0, 0], dtype=np.uint16)
        header.tofile (f)
        buffer.tofile(f)


def unwrap_workflow(config):

    # load tiff image-stack and calculate unwrapped phase-maps
    #
    working_directory = config["working_directory"]
    filename = "cam_pos00.tiff"
    path = os.path.join(working_directory, filename)
    if not os.path.exists(path):
        print(f"file '{path}' not exists, aborting." )
        return

    print("read camera images from multi page tiff stack '{}'".format(filename))
    retval, imagestack = cv2.imreadmulti(filename, flags=cv2.IMREAD_GRAYSCALE)
    assert retval

    phase, modulation = unwrap.unwrap(config, imagestack)
    np.save(os.path.join(working_directory, "phi_unwrapped.npy"), phase[0])
    np.save(os.path.join(working_directory, "phi_modulation.npy"), modulation[0])
    np.save(os.path.join(working_directory, "eta_unwrapped.npy"), phase[1])
    np.save(os.path.join(working_directory, "eta_modulation.npy"), modulation[1])

    save_float_big(os.path.join(working_directory, "phi_unwrapped.big"), phase[0].astype(np.float32))
    save_float_big(os.path.join(working_directory, "phi_modulation.big"), modulation[0].astype(np.float32))
    save_float_big(os.path.join(working_directory, "eta_unwrapped.big"), phase[1].astype(np.float32))
    save_float_big(os.path.join(working_directory, "eta_modulation.big"), modulation[1].astype(np.float32))

    # plot unwrapped phase-maps and modulation
    #

    import matplotlib.pyplot as plt
    from matplotlib import cm
    from mpl_toolkits.axes_grid1 import make_axes_locatable

    fig = plt.figure(figsize=(13.5, 9), dpi=80)
    fig.suptitle(f"modulation images and phase maps")

    ax_mod_x = fig.add_subplot(221)
    im_mod_x = ax_mod_x.imshow(modulation[0], cmap=cm.viridis)
    ax_mod_x.set_xlabel("$x$ (px)")
    ax_mod_x.set_ylabel("$y$ (px)")

    ax_phi_x = fig.add_subplot(222)
    im_phi_x = ax_phi_x.imshow(phase[0], 
        vmin=np.nanpercentile(phase[0], 5), 
        vmax=np.nanpercentile(phase[0], 95), 
        cmap=cm.jet)
    ax_phi_x.set_xlabel("$x$ (px)")
    ax_phi_x.set_ylabel("$y$ (px)")

    ax_mod_y = fig.add_subplot(223)
    im_mod_y = ax_mod_y.imshow(modulation[1], cmap=cm.viridis)
    ax_mod_y.set_xlabel("$x$ (px)")
    ax_mod_y.set_ylabel("$y$ (px)")

    ax_phi_y = fig.add_subplot(224)
    im_phi_y = ax_phi_y.imshow(phase[1], 
        vmin=np.nanpercentile(phase[1], 5), 
        vmax=np.nanpercentile(phase[1], 95), 
        cmap=cm.jet)
    ax_phi_y.set_xlabel("$x$ (px)")
    ax_phi_y.set_ylabel("$y$ (px)")

    divider_mod_x = make_axes_locatable(ax_mod_x)
    cbax_mod_x = divider_mod_x.append_axes("right", size="5%", pad=0.1)
    fig.colorbar(im_mod_x, cax=cbax_mod_x, label="modulation from horizontal images")

    divider_phi_x = make_axes_locatable(ax_phi_x)
    cbax_phi_x = divider_phi_x.append_axes("right", size="5%", pad=0.1)
    fig.colorbar(im_phi_x, cax=cbax_phi_x, label="phase-map $\phi_x$ from horizontal images")

    divider_mod_y = make_axes_locatable(ax_mod_y)
    cbax_mod_y = divider_mod_y.append_axes("right", size="5%", pad=0.1)
    fig.colorbar(im_mod_y, cax=cbax_mod_y, label="modulation from vertical images")

    divider_phi_y = make_axes_locatable(ax_phi_y)
    cbax_phi_y = divider_phi_y.append_axes("right", size="5%", pad=0.1)
    fig.colorbar(im_phi_y, cax=cbax_phi_y, label="phase-map $\phi_y$ from vertical images")

    plt.subplots_adjust(left=0.07, bottom=0.1, right=0.93, top=0.95, wspace=0.35)
    plt.show()



def flatness_deviation_workflow(config, polynomial_fitting_degree = 6):

    working_directory = config["working_directory"]
    filenames = [
        os.path.join(working_directory, "phi_unwrapped.npy"),
        os.path.join(working_directory, "eta_unwrapped.npy")]

    print(f"load phase maps: {filenames}")
    phase = np.array([np.load(filenames[0]), np.load(filenames[1])])

    fitted_polynomial_coefficients = np.array([
            unwrap.poly_coeffs(phase[0], polynomial_fitting_degree),
            unwrap.poly_coeffs(phase[1], polynomial_fitting_degree),
        ])

    dev = np.array([
        unwrap.poly_dev(phase[0], fitted_polynomial_coefficients[0], polynomial_fitting_degree),
        unwrap.poly_dev(phase[1], fitted_polynomial_coefficients[1], polynomial_fitting_degree)
        ])

    np.save(os.path.join(working_directory, "phi_deviation.npy"), dev[0])
    np.save(os.path.join(working_directory, "eta_deviation.npy"), dev[1])

    save_float_big(os.path.join(working_directory, "phi_deviation.big"), dev[0].astype(np.float32))
    save_float_big(os.path.join(working_directory, "eta_deviation.big"), dev[1].astype(np.float32))

    import matplotlib.pyplot as plt
    from matplotlib import cm
    from mpl_toolkits.axes_grid1 import make_axes_locatable

    fig = plt.figure(figsize=(18, 13), dpi=80)
    fig.suptitle(f"phase-maps and flatness deviation with polynomial fitting degree: {polynomial_fitting_degree}")

    ax_phi_x = fig.add_subplot(221)
    im_phi_x = ax_phi_x.imshow(phase[0], 
        vmin=np.nanpercentile(phase[0], 5),
        vmax=np.nanpercentile(phase[0], 95), 
        cmap=cm.jet)

    ax_phi_x.set_xlabel("$x$ (px)")
    ax_phi_x.set_ylabel("$y$ (px)")

    ax_dev_x = fig.add_subplot(222)
    im_dev_x = ax_dev_x.imshow(dev[0], 
        vmin=np.nanpercentile(dev[0], 5), 
        vmax=np.nanpercentile(dev[0], 95), 
        cmap=cm.viridis)

    ax_dev_x.set_xlabel("$x$ (px)")
    ax_dev_x.set_ylabel("$y$ (px)")

    ax_phi_y = fig.add_subplot(223)
    im_phi_y = ax_phi_y.imshow(phase[1], 
        vmin=np.nanpercentile(phase[1], 5), 
        vmax=np.nanpercentile(phase[1], 95), 
        cmap=cm.jet)

    ax_phi_y.set_xlabel("$x$ (px)")
    ax_phi_y.set_ylabel("$y$ (px)")

    ax_dev_y = fig.add_subplot(224)
    im_dev_y = ax_dev_y.imshow(dev[1],
        vmin=np.nanpercentile(dev[1], 5),
        vmax=np.nanpercentile(dev[1], 95),
        cmap=cm.viridis)

    ax_dev_y.set_xlabel("$x$ (px)")
    ax_dev_y.set_ylabel("$y$ (px)")

    fig.colorbar(im_phi_x, ax=ax_phi_x, label="horizontal phase-map $\phi_x$", 
        fraction=0.035, pad=0.04, shrink=0.8)
    fig.colorbar(im_dev_x, ax=ax_dev_x, label="horizontal difference phase-map $\delta_x$", 
        fraction=0.035, pad=0.04, shrink=0.8)
    fig.colorbar(im_phi_y, ax=ax_phi_y, label="vertical phase-map $\phi_y$", 
        fraction=0.035, pad=0.04, shrink=0.8)
    fig.colorbar(im_dev_y, ax=ax_dev_y, label="vertical difference phase-map $\delta_y$", 
        fraction=0.035, pad=0.04, shrink=0.8)

    plt.subplots_adjust(left=0.07, bottom=0.1, right=0.93, top=0.95, wspace=0.35)
    plt.show()


if __name__ == '__main__':

    print("np.__version__ {}", np.__version__)
    print("cv2.__version__ {}", cv2.__version__)

    projector_img_width, projector_img_height = 1280,800
    sine_period_length_x, sine_period_length_y = 16,16
    working_directory = "."

    config = {
        "working_directory": working_directory,
        "projector_img_width": 1280,
        "projector_img_height": 800,
        "sine_period_length_x": 16,
        "sine_period_length_y": 16,
        "sine_patterns_x": 16,
        "sine_patterns_y": 16,
        "gc_patterns_x": int(np.ceil(np.log2(projector_img_width /(.5*sine_period_length_x)))),
        "gc_patterns_y": int(np.ceil(np.log2(projector_img_height/(.5*sine_period_length_y)))),
        "modulation_threshold": 4
    }

    unwrap_workflow(config)
    flatness_deviation_workflow(config)
