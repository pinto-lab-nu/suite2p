"""
Copyright © 2023 Howard Hughes Medical Institute, Authored by Carsen Stringer and Marius Pachitariu.
"""
import gc
import glob
import json
import math
import os
import time
from typing import Union, Tuple, Optional

import numpy as np
from tifffile import imread, TiffFile, TiffWriter

from . import utils

try:
    from ScanImageTiffReader import ScanImageTiffReader
    HAS_SCANIMAGE = True
except ImportError:
    ScanImageTiffReader = None
    HAS_SCANIMAGE = False


def generate_tiff_filename(functional_chan: int, align_by_chan: int, save_path: str,
                           k: int, ichan: bool) -> str:
    """
    Calculates a suite2p tiff filename from different parameters.

    Parameters
    ----------
    functional_chan: int
        The channel number with functional information
    align_by_chan: int
        Which channel to use for alignment
    save_path: str
        The directory to save to
    k: int
        The file number
    wchan: int
        The channel number.

    Returns
    -------
    filename: str
    """
    if ichan:
        if functional_chan == align_by_chan:
            tifroot = os.path.join(save_path, "reg_tif")
            wchan = 0
        else:
            tifroot = os.path.join(save_path, "reg_tif_chan2")
            wchan = 1
    else:
        if functional_chan == align_by_chan:
            tifroot = os.path.join(save_path, "reg_tif_chan2")
            wchan = 1
        else:
            tifroot = os.path.join(save_path, "reg_tif")
            wchan = 0
    if not os.path.isdir(tifroot):
        os.makedirs(tifroot)
    fname = "file00%0.3d_chan%d.tif" % (k, wchan)
    fname = os.path.join(tifroot, fname)
    return fname


def save_tiff(mov: np.ndarray, fname: str) -> None:
    """
    Save image stack array to tiff file.

    Parameters
    ----------
    mov: nImg x Ly x Lx
        The frames to save
    fname: str
        The tiff filename to save to

    """
    with TiffWriter(fname) as tif:
        for frame in np.floor(mov).astype(np.int16):
            tif.write(frame, contiguous=True)


def open_tiff(file: str,
              sktiff: bool) -> Tuple[Union[TiffFile, ScanImageTiffReader], int]:
    """ Returns image and its length from tiff file with either ScanImageTiffReader or tifffile, based on "sktiff" """
    if sktiff:
        tif = TiffFile(file)
        Ltif = len(tif.pages)
    else:
        tif = ScanImageTiffReader(file)
        Ltif = 1 if len(tif.shape()) < 3 else tif.shape()[0]  # single page tiffs
    return tif, Ltif


def use_sktiff_reader(tiff_filename, batch_size: Optional[int] = None) -> bool:
    """Returns False if ScanImageTiffReader works on the tiff file, else True (in which case use tifffile)."""
    if HAS_SCANIMAGE:
        try:
            with ScanImageTiffReader(tiff_filename) as tif:
                tif.data() if len(tif.shape()) < 3 else tif.data(
                    beg=0, end=np.minimum(batch_size,
                                          tif.shape()[0] - 1))
            return False
        except:
            print(
                "NOTE: ScanImageTiffReader not working for this tiff type, using tifffile"
            )
            return True
    else:
        print("NOTE: ScanImageTiffReader not installed, using tifffile")
        return True

def read_tiff(file, tif, Ltif, ix, batch_size, use_sktiff):
    # tiff reading
    if ix >= Ltif:
        return None
    nfr = min(Ltif - ix, batch_size)
    if use_sktiff:
        im = imread(file, key=range(ix, ix + nfr))
    elif Ltif == 1:
        im = tif.data()
    else:
        im = tif.data(beg=ix, end=ix + nfr)
    # for single-page tiffs, add 1st dim
    if len(im.shape) < 3:
        im = np.expand_dims(im, axis=0)

    # check if uint16
    if im.dtype.type == np.uint16:
        im = (im // 2).astype(np.int16)
    elif im.dtype.type == np.int32:
        im = (im // 2).astype(np.int16)
    elif im.dtype.type != np.int16:
        im = im.astype(np.int16)

    if im.shape[0] > nfr:
        im = im[:nfr, :, :]

    return im

def tiff_to_binary(ops):
    """  finds tiff files and writes them to binaries

    Parameters
    ----------
    ops : dictionary
        "nplanes", "data_path", "save_path", "save_folder", "fast_disk", "nchannels", "keep_movie_raw", "look_one_level_down"

    Returns
    -------
        ops : dictionary of first plane
            ops["reg_file"] or ops["raw_file"] is created binary
            assigns keys "Ly", "Lx", "tiffreader", "first_tiffs",
            "frames_per_folder", "nframes", "meanImg", "meanImg_chan2"

    """

    t0 = time.time()

    # copy ops to list where each element is ops for each plane
    # copy ops to list where each element is ops for each plane
    ops1 = utils.init_ops(ops)
    nplanes = ops1[0]["nplanes"]
    nchannels = ops1[0]["nchannels"]

    print('Running {} planes and {} channels'.format(nplanes,nchannels))

    # open all binary files for writing and look for tiffs in all requested folders
    ops1, fs, reg_file, reg_file_chan2 = utils.find_files_open_binaries(ops1, False)
    isbruker = ops1[0]['bruker']
    recpath  = ops1[0]['save_path0']
    ops      = ops1[0]

    if isbruker:
        xmlfile   = utils.infer_bruker_xml_filename(ops['data_path'][0])
        frameinfo = utils.frame_info_from_bruker_xml(xmlfile)

    # try tiff readers
    use_sktiff = True if ops["force_sktiff"] else use_sktiff_reader(
        fs[0], batch_size=ops1[0].get("batch_size"))

    batch_size = ops["batch_size"]
    if ~isbruker:
        batch_size = nplanes * nchannels * math.ceil(batch_size / (nplanes * nchannels))

    # loop over all tiffs
    which_folder = -1
    ntotal = 0
    plane_ct = np.zeros(nplanes)
    
    for ik, file in enumerate(fs):
        # open tiff
        # print('opening file {}'.format(file))
        tif, Ltif = open_tiff(file, use_sktiff)
        # keep track of the plane identity of the first frame (channel identity is assumed always 0)
        if isbruker:
            plane_order = frameinfo['fov_ids'][(nplanes*ik):(nplanes*ik+nplanes)]
            # iplane   = frameinfo['fov_ids'][ik] 
            ichannel = frameinfo['channel_ids'][ik]
            if ops['first_tiffs'][ik]:
                which_folder += 1
 
        else:
            # keep track of the plane identity of the first frame (channel identity is assumed always 0)
            plane_order = [0]
            if ops['first_tiffs'][ik]:
                which_folder += 1
                iplane = 0

        # ix = iplane

        ix = 0
        # plane_idx = 0
        while 1:
            # tiff reading
            im = read_tiff(file, tif, Ltif, ix, batch_size, use_sktiff)
            if im is None:
                break


            nframes = im.shape[0]
            # nframes = im.shape[0] / Ltif if Ltif > 0 else im.shape[0]
            for plane_idx in plane_order:
                iplane = plane_order[plane_idx] if isbruker else iplane

                if nplanes > 1:
                    current_im = im[plane_idx:plane_idx+1, :, :]
                else:
                    current_im = im

                if isbruker:
                    if plane_ct[iplane]==0:
                        ops1[iplane]['nframes'] = 0
                        ops1[iplane]['frames_per_file'] = np.zeros((len(fs),), dtype=int)
                        ops1[iplane]['meanImg'] = np.zeros((current_im.shape[1], current_im.shape[2]), np.float32)

                        # This if block is not debugged yet
                        if nchannels>1:
                            ops1[iplane]['meanImg_chan2'] = np.zeros((im.shape[1], im.shape[2]), np.float32)

                    # Multi-channel not yet fixed for 2 planes
                    if nchannels>1:
                        if ichannel == ops['functional_chan']:
                            reg_file[iplane].write(bytearray(im))
                            ops1[iplane]['meanImg'] += im.astype(np.float32).sum(axis=0)
                            ops1[iplane]['nframes'] += im.shape[0]
                            ops1[iplane]['frames_per_file'][int(plane_ct[iplane])] += im.shape[0]
                            ops1[iplane]['frames_per_folder'][which_folder] += im.shape[0]
    
                        else:
                            reg_file_chan2[iplane].write(bytearray(im))
                            ops1[iplane]['meanImg_chan2'] += im.mean(axis=0)

                    else:
                        reg_file[iplane].write(bytearray(current_im))
                        ops1[iplane]['meanImg'] += current_im.astype(np.float32).sum(axis=0)
                        ops1[iplane]['nframes'] += current_im.shape[0]
                        # ops1[iplane]['frames_per_file'][int(plane_ct[iplane])] += current_im.shape[0]
                        ops1[iplane]['frames_per_file'][ik] += current_im.shape[0]
                        ops1[iplane]['frames_per_folder'][which_folder] += current_im.shape[0]
                    
                    plane_ct[iplane] += current_im.shape[0] # assumes each tif "stack" is from single plane

                else:
                    for j in range(0, nplanes):
                        if ik == 0 and ix == 0:
                            ops1[j]["nframes"] = 0
                            ops1[j]["frames_per_file"] = np.zeros((len(fs),), dtype=int)
                            ops1[j]["meanImg"] = np.zeros((im.shape[1], im.shape[2]),
                                                        np.float32)
                            if nchannels > 1:
                                ops1[j]["meanImg_chan2"] = np.zeros((im.shape[1], im.shape[2]),
                                                                    np.float32)
                        i0 = nchannels * ((iplane + j) % nplanes)
                        if nchannels > 1:
                            nfunc = ops["functional_chan"] - 1
                        else:
                            nfunc = 0
                        im2write = im[int(i0) + nfunc:nframes:nplanes * nchannels]

                        reg_file[j].write(bytearray(im2write))
                        ops1[j]["meanImg"] += im2write.astype(np.float32).sum(axis=0)
                        ops1[j]["nframes"] += im2write.shape[0]
                        ops1[j]["frames_per_file"][ik] += im2write.shape[0]
                        ops1[j]["frames_per_folder"][which_folder] += im2write.shape[0]
                        #print(ops1[j]["frames_per_folder"][which_folder])
                        if nchannels > 1:
                            im2write = im[int(i0) + 1 - nfunc:nframes:nplanes * nchannels]
                            reg_file_chan2[j].write(bytearray(im2write))
                            ops1[j]["meanImg_chan2"] += im2write.mean(axis=0)
                    iplane = (iplane - nframes / nchannels) % nplanes
                
            ix += nframes
            ntotal += nframes
            if ntotal % (batch_size * 4) == 0:
                print("%d frames of binary, time %0.2f sec." %
                    (ntotal, time.time() - t0))
    gc.collect()
    # write ops files
    do_registration = ops["do_registration"]
    for ops in ops1:
        ops["Ly"], ops["Lx"] = ops["meanImg"].shape
        ops["yrange"] = np.array([0, ops["Ly"]])
        ops["xrange"] = np.array([0, ops["Lx"]])
        ops["meanImg"] /= ops["nframes"]
        if nchannels > 1:
            ops["meanImg_chan2"] /= ops["nframes"]
        np.save(ops["ops_path"], ops)
    # close all binary files and write ops files
    for j in range(0, nplanes):
        reg_file[j].close()
        if nchannels > 1:
            reg_file_chan2[j].close()
    return ops1[0]


def mesoscan_to_binary(ops):
    """ finds mesoscope tiff files and writes them to binaries

    Parameters
    ----------
    ops : dictionary
        "nplanes", "data_path", "save_path", "save_folder", "fast_disk",
        "nchannels", "keep_movie_raw", "look_one_level_down", "lines", "dx", "dy"

    Returns
    -------
        ops : dictionary of first plane
            ops["reg_file"] or ops["raw_file"] is created binary
            assigns keys "Ly", "Lx", "tiffreader", "first_tiffs", "frames_per_folder",
            "nframes", "meanImg", "meanImg_chan2"

    """
    t0 = time.time()
    if "lines" not in ops:
        fpath = os.path.join(ops["data_path"][0], "*json")
        fs = glob.glob(fpath)
        with open(fs[0], "r") as f:
            opsj = json.load(f)
        if "nrois" in opsj:
            ops["nrois"] = opsj["nrois"]
            ops["nplanes"] = opsj["nplanes"]
            ops["dy"] = opsj["dy"]
            ops["dx"] = opsj["dx"]
            ops["fs"] = opsj["fs"]
        elif "nplanes" in opsj and "lines" in opsj:
            ops["nrois"] = opsj["nplanes"]
            ops["nplanes"] = 1
        else:
            ops["nplanes"] = len(opsj)
        ops["lines"] = opsj["lines"]
    else:
        ops["nrois"] = len(ops["lines"])
    nplanes = ops["nplanes"]

    print("NOTE: nplanes %d nrois %d => ops['nplanes'] = %d" %
          (nplanes, ops["nrois"], ops["nrois"] * nplanes))
    # multiply lines across planes
    lines = ops["lines"].copy()
    dy = ops["dy"].copy()
    dx = ops["dx"].copy()
    ops["lines"] = [None] * nplanes * ops["nrois"]
    ops["dy"] = [None] * nplanes * ops["nrois"]
    ops["dx"] = [None] * nplanes * ops["nrois"]
    ops["iplane"] = np.zeros((nplanes * ops["nrois"],), np.int32)
    for n in range(ops["nrois"]):
        ops["lines"][n::ops["nrois"]] = [lines[n]] * nplanes
        ops["dy"][n::ops["nrois"]] = [dy[n]] * nplanes
        ops["dx"][n::ops["nrois"]] = [dx[n]] * nplanes
        ops["iplane"][n::ops["nrois"]] = np.arange(0, nplanes, 1, int)
    ops["nplanes"] = nplanes * ops["nrois"]
    ops1 = utils.init_ops(ops)

    # this shouldn"t make it here
    if "lines" not in ops:
        for j in range(len(ops1)):
            ops1[j] = {**ops1[j], **opsj[j]}.copy()

    # open all binary files for writing
    # look for tiffs in all requested folders
    ops1, fs, reg_file, reg_file_chan2 = utils.find_files_open_binaries(ops1, False)
    ops = ops1[0]

    nchannels = ops1[0]["nchannels"]
    batch_size = ops["batch_size"]

    # which tiff reader works for user"s tiffs
    use_sktiff = True if ops["force_sktiff"] else use_sktiff_reader(
        fs[0], batch_size=ops1[0].get("batch_size"))

    # loop over all tiffs
    which_folder = -1
    ntotal = 0
    for ik, file in enumerate(fs):
        # open tiff
        tif, Ltif = open_tiff(file, use_sktiff)
        if ops["first_tiffs"][ik]:
            which_folder += 1
            iplane = 0
        ix = 0
        while 1:
            if ix >= Ltif:
                break
            nfr = min(Ltif - ix, batch_size)
            if use_sktiff:
                im = imread(file, key=range(ix, ix + nfr))
            else:
                if Ltif == 1:
                    im = tif.data()
                else:
                    im = tif.data(beg=ix, end=ix + nfr)
            if im.size == 0:
                break

            if len(im.shape) < 3:
                im = np.expand_dims(im, axis=0)

            if im.shape[0] > nfr:
                im = im[:nfr, :, :]
            nframes = im.shape[0]

            for j in range(0, ops["nplanes"]):
                jlines = np.array(ops1[j]["lines"]).astype(np.int32)
                jplane = ops1[j]["iplane"]
                if ik == 0 and ix == 0:
                    ops1[j]["meanImg"] = np.zeros((len(jlines), im.shape[2]),
                                                  np.float32)
                    if nchannels > 1:
                        ops1[j]["meanImg_chan2"] = np.zeros((len(jlines), im.shape[2]),
                                                            np.float32)
                    ops1[j]["nframes"] = 0
                i0 = nchannels * ((iplane + jplane) % nplanes)
                if nchannels > 1:
                    nfunc = ops["functional_chan"] - 1
                else:
                    nfunc = 0
                #frange = np.arange(int(i0)+nfunc, nframes, nplanes*nchannels)
                im2write = im[int(i0) + nfunc:nframes:nplanes * nchannels,
                              jlines[0]:(jlines[-1] + 1), :]
                #im2write = im[np.ix_(frange, jlines, np.arange(0,im.shape[2],1,int))]
                ops1[j]["meanImg"] += im2write.astype(np.float32).sum(axis=0)
                reg_file[j].write(bytearray(im2write))
                ops1[j]["nframes"] += im2write.shape[0]
                ops1[j]["frames_per_folder"][which_folder] += im2write.shape[0]
                if nchannels > 1:
                    frange = np.arange(
                        int(i0) + 1 - nfunc, nframes, nplanes * nchannels)
                    im2write = im[np.ix_(frange, jlines,
                                         np.arange(0, im.shape[2], 1, int))]
                    reg_file_chan2[j].write(bytearray(im2write))
                    ops1[j]["meanImg_chan2"] += im2write.astype(np.float32).sum(axis=0)
            iplane = (iplane - nframes / nchannels) % nplanes
            ix += nframes
            ntotal += nframes
            if ops1[0]["nframes"] % (batch_size * 4) == 0:
                print("%d frames of binary, time %0.2f sec." %
                      (ops1[0]["nframes"], time.time() - t0))
        gc.collect()
    # write ops files
    do_registration = ops["do_registration"]
    for ops in ops1:
        ops["Ly"], ops["Lx"] = ops["meanImg"].shape
        if not do_registration:
            ops["yrange"] = np.array([0, ops["Ly"]])
            ops["xrange"] = np.array([0, ops["Lx"]])
        ops["meanImg"] /= ops["nframes"]
        if nchannels > 1:
            ops["meanImg_chan2"] /= ops["nframes"]
        np.save(ops["ops_path"], ops)
    # close all binary files and write ops files
    for j in range(0, ops["nplanes"]):
        reg_file[j].close()
        if nchannels > 1:
            reg_file_chan2[j].close()
    return ops1[0]


def ome_to_binary(ops):
    """
    converts ome.tiff to *.bin file for non-interleaved red channel recordings
    assumes SINGLE-PAGE tiffs where first channel has string "Ch1"
    and also SINGLE FOLDER

    Parameters
    ----------
    ops : dictionary
        keys nplanes, nchannels, data_path, look_one_level_down, reg_file

    Returns
    -------
    ops : dictionary of first plane
        creates binaries ops["reg_file"]
        assigns keys: tiffreader, first_tiffs, frames_per_folder, nframes, meanImg, meanImg_chan2
    """
    t0 = time.time()

    # copy ops to list where each element is ops for each plane
    ops1 = utils.init_ops(ops)
    nplanes = ops1[0]["nplanes"]

    # open all binary files for writing and look for tiffs in all requested folders
    ops1, fs, reg_file, reg_file_chan2 = utils.find_files_open_binaries(ops1, False)
    ops = ops1[0]
    isbruker = ops1[0]['bruker']
    batch_size = ops["batch_size"]
    use_sktiff = not HAS_SCANIMAGE

    fs_Ch1, fs_Ch2 = [], []
    if isbruker:
 
        xmlfile   = utils.infer_bruker_xml_filename(ops['data_path'][0])
 
        frameinfo = utils.frame_info_from_bruker_xml(xmlfile)
 
        if ops['functional_chan'] == 1:
 
            fs_Ch1   = f[frameinfo['channel_ids']==1]
 
            fs_Ch2   = f[frameinfo['channel_ids']==2]
 
            func_idx = frameinfo['channel_ids']==1
 
        else:
 
            fs_Ch1   = f[frameinfo['channel_ids']==2]
 
            fs_Ch2   = f[frameinfo['channel_ids']==1]
 
            func_idx = frameinfo['channel_ids']==2
 
    else:
        for f in fs:
            if f.find("Ch1") > -1:
                if ops["functional_chan"] == 1:
                    fs_Ch1.append(f)
                else:
                    fs_Ch2.append(f)
            else:
                if ops["functional_chan"] == 1:
                    fs_Ch2.append(f)
                else:
                    fs_Ch1.append(f)

    if len(fs_Ch2) == 0:
        ops1[0]["nchannels"] = 1
    nchannels = ops1[0]["nchannels"]
    print(f"nchannels = {nchannels}")
    
    # loop over all tiffs
    TiffReader = ScanImageTiffReader if HAS_SCANIMAGE else TiffFile
    with TiffReader(fs_Ch1[0]) as tif:
        if HAS_SCANIMAGE:
            n_pages = tif.shape()[0] if len(tif.shape()) > 2 else 1
            shape = tif.shape()[-2:]
        else:
            n_pages = len(tif.pages)
            im0 = tif.pages[0].asarray()
            shape = im0.shape
    
    for ops1_0 in ops1:
        ops1_0["nframes"] = 0
        ops1_0["frames_per_folder"][0] = 0
        ops1_0["frames_per_file"] = np.ones(len(fs_Ch1), "int") if n_pages==1 else np.zeros(len(fs_Ch1), "int")
        ops1_0["meanImg"] = np.zeros(shape, np.float32)
        if nchannels > 1:
            ops1_0["meanImg_chan2"] = np.zeros(shape, np.float32)
    if isbruker: 
        iplanes = frameinfo['fov_ids'][func_idx]
 
    else:
        bruker_bidirectional = ops.get("bruker_bidirectional", False)
        iplanes = np.arange(0, nplanes)
        if not bruker_bidirectional:
            iplanes = np.tile(iplanes[np.newaxis, :],
                            int(np.ceil(len(fs_Ch1) / nplanes))).flatten()
            iplanes = iplanes[:len(fs_Ch1)]
        else:
            iplanes = np.hstack((iplanes, iplanes[::-1]))
            iplanes = np.tile(iplanes[np.newaxis, :],
                            int(np.ceil(len(fs_Ch1) / (2 * nplanes)))).flatten()
            iplanes = iplanes[:len(fs_Ch1)]

    itot = 0
    for ik, file in enumerate(fs_Ch1):
        ip = iplanes[ik]
        # read tiff
        if n_pages==1:    
            with TiffReader(file) as tif:
                im = tif.data()  if HAS_SCANIMAGE else tif.pages[0].asarray()
            if im.dtype.type == np.uint16:
                im = (im // 2)
            im = im.astype(np.int16)

            # write to binary
            ops1[ip]["nframes"] += 1
            ops1[ip]["frames_per_folder"][0] += 1
            ops1[ip]["meanImg"] += im.astype(np.float32)
            reg_file[ip].write(bytearray(im))
            #gc.collect()
        else:
            tif, Ltif = open_tiff(file, not HAS_SCANIMAGE)
            # keep track of the plane identity of the first frame (channel identity is assumed always 0)
            ix = 0
            while 1:
                im = read_tiff(file, tif, Ltif, ix, batch_size, use_sktiff)
                if im is None:
                    break          
                nframes = im.shape[0]
                ix += nframes
                itot += nframes
                reg_file[ip].write(bytearray(im))
                ops1[ip]["meanImg"] += im.astype(np.float32).sum(axis=0)
                ops1[ip]["nframes"] += im.shape[0]
                ops1[ip]["frames_per_file"][ik] += nframes
                ops1[ip]["frames_per_folder"][0] += nframes
                if itot % 1000 == 0:
                    print("%d frames of binary, time %0.2f sec." % (itot, time.time() - t0))
                gc.collect()            

    if nchannels > 1:
        itot = 0
        for ik, file in enumerate(fs_Ch2):
            ip = iplanes[ik]
            if n_pages==1:
                with TiffReader(file) as tif:
                    im = tif.data() if HAS_SCANIMAGE else tif.pages[0].asarray()
                if im.dtype.type == np.uint16:
                    im = (im // 2)
                im = im.astype(np.int16)
                ops1[ip]["meanImg_chan2"] += im.astype(np.float32)
                reg_file_chan2[ip].write(bytearray(im))
            else:
                tif, Ltif = open_tiff(file, not HAS_SCANIMAGE)
                ix = 0
                while 1:
                    im = read_tiff(file, tif, Ltif, ix, batch_size, use_sktiff)
                    if im is None:
                        break          
                    nframes = im.shape[0]
                    ix += nframes
                    itot += nframes
                    ops1[ip]["meanImg_chan2"] += im.astype(np.float32).sum(axis=0)
                    reg_file_chan2[ip].write(bytearray(im))
                    if itot % 1000 == 0:
                        print("%d frames of binary, time %0.2f sec." % (itot, time.time() - t0))
                    gc.collect()

    # write ops files
    do_registration = ops["do_registration"]
    for ops in ops1:
        ops["Ly"], ops["Lx"] = shape
        if not do_registration:
            ops["yrange"] = np.array([0, ops["Ly"]])
            ops["xrange"] = np.array([0, ops["Lx"]])
        ops["meanImg"] /= ops["nframes"]
        if nchannels > 1:
            ops["meanImg_chan2"] /= ops["nframes"]
        np.save(ops["ops_path"], ops)
    # close all binary files and write ops files
    for j in range(0, nplanes):
        reg_file[j].close()
        if nchannels > 1:
            reg_file_chan2[j].close()
    return ops1[0]
