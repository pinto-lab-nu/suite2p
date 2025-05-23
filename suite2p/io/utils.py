"""
Copyright © 2023 Howard Hughes Medical Institute, Authored by Carsen Stringer and Marius Pachitariu.
"""
import glob
import os
from pathlib import Path

import numpy as np
import xml.etree.ElementTree as et
from natsort import natsorted


def search_for_ext(rootdir, extension="tif", look_one_level_down=False):
    filepaths = []
    if os.path.isdir(rootdir):
        # search root dir
        tmp = glob.glob(os.path.join(rootdir, "*." + extension))
        if len(tmp):
            filepaths.extend([t for t in natsorted(tmp)])
        # search one level down
        if look_one_level_down:
            dirs = natsorted(os.listdir(rootdir))
            for d in dirs:
                if os.path.isdir(os.path.join(rootdir, d)):
                    tmp = glob.glob(os.path.join(rootdir, d, "*." + extension))
                    if len(tmp):
                        filepaths.extend([t for t in natsorted(tmp)])
    if len(filepaths):
        return filepaths
    else:
        raise OSError("Could not find files, check path [{0}]".format(rootdir))


def get_sbx_list(ops):
    """ make list of scanbox files to process
    if ops["subfolders"], then all tiffs ops["data_path"][0] / ops["subfolders"] / *.sbx
    if ops["look_one_level_down"], then all tiffs in all folders + one level down
    TODO: Implement "tiff_list" functionality
    """
    froot = ops["data_path"]
    # use a user-specified list of tiffs
    if len(froot) == 1:
        if "subfolders" in ops and len(ops["subfolders"]) > 0:
            fold_list = []
            for folder_down in ops["subfolders"]:
                fold = os.path.join(froot[0], folder_down)
                fold_list.append(fold)
        else:
            fold_list = ops["data_path"]
    else:
        fold_list = froot
    fsall = []
    for k, fld in enumerate(fold_list):
        fs = search_for_ext(fld, extension="sbx",
                            look_one_level_down=ops["look_one_level_down"])
        fsall.extend(fs)
    if len(fsall) == 0:
        print(fold_list)
        raise Exception("No files, check path.")
    else:
        print("** Found %d sbx - converting to binary **" % (len(fsall)))
    return fsall, ops

def get_movie_list(ops):
    """ make list of movie files to process
    if ops["subfolders"], then all  ops["data_path"][0] / ops["subfolders"] / *.avi or *.mp4
    if ops["look_one_level_down"], then all tiffs in all folders + one level down
    """
    froot = ops["data_path"]
    # use a user-specified list of tiffs
    if len(froot) == 1:
        if "subfolders" in ops and len(ops["subfolders"]) > 0:
            fold_list = []
            for folder_down in ops["subfolders"]:
                fold = os.path.join(froot[0], folder_down)
                fold_list.append(fold)
        else:
            fold_list = ops["data_path"]
    else:
        fold_list = froot
    fsall = []
    for k, fld in enumerate(fold_list):
        try:
            fs = search_for_ext(fld, extension="mp4",
                                look_one_level_down=ops["look_one_level_down"])
            fsall.extend(fs)
        except:
            fs = search_for_ext(fld, extension="avi",
                                look_one_level_down=ops["look_one_level_down"])
            fsall.extend(fs)
    if len(fsall) == 0:
        print(fold_list)
        raise Exception("No files, check path.")
    else:
        print("** Found %d movies - converting to binary **" % (len(fsall)))
    return fsall, ops



def list_h5(ops):
    froot = os.path.dirname(ops["h5py"])
    lpath = os.path.join(froot, "*.h5")
    fs = natsorted(glob.glob(lpath))
    lpath = os.path.join(froot, "*.hdf5")
    fs2 = natsorted(glob.glob(lpath))
    fs.extend(fs2)
    return fs


def list_files(froot, look_one_level_down, exts):
    """ get list of files with exts in folder froot + one level down maybe
    """
    fs = []
    for e in exts:
        lpath = os.path.join(froot, e)
        fs.extend(glob.glob(lpath))
    fs = natsorted(set(fs))
    if len(fs) > 0:
        first_tiffs = np.zeros((len(fs),), "bool")
        first_tiffs[0] = True
    else:
        first_tiffs = np.zeros(0, "bool")
    lfs = len(fs)
    if look_one_level_down:
        fdir = natsorted(glob.glob(os.path.join(froot, "*/")))
        for folder_down in fdir:
            fsnew = []
            for e in exts:
                lpath = os.path.join(folder_down, e)
                fsnew.extend(glob.glob(lpath))
            fsnew = natsorted(set(fsnew))
            if len(fsnew) > 0:
                fs.extend(fsnew)
                first_tiffs = np.append(first_tiffs, np.zeros((len(fsnew),), "bool"))
                first_tiffs[lfs] = True
                lfs = len(fs)
    return fs, first_tiffs


def get_h5_list(ops):
    """ make list of h5 files to process
    if ops["look_one_level_down"], then all h5"s in all folders + one level down
    """
    froot = ops["data_path"]
    fold_list = ops["data_path"]
    fsall = []
    nfs = 0
    first_tiffs = []
    for k, fld in enumerate(fold_list):
        fs, ftiffs = list_files(fld, ops["look_one_level_down"], 
                                ["*.h5", "*.hdf5", "*.mesc"])
        fsall.extend(fs)
        first_tiffs.extend(list(ftiffs))
    #if len(fs) > 0 and not isinstance(fs, list):
    #    fs = [fs]
    if len(fs) == 0:
        print("Could not find any h5 files")
        raise Exception("no h5s")
    else:
        ops["first_tiffs"] = np.array(first_tiffs).astype("bool")
        print("** Found %d h5 files - converting to binary **" % (len(fsall)))
        #print("Found %d tifs"%(len(fsall)))
    return fsall, ops


def get_tif_list(ops):
    """ make list of tiffs to process
    if ops["subfolders"], then all tiffs ops["data_path"][0] / ops["subfolders"] / *.tif
    if ops["look_one_level_down"], then all tiffs in all folders + one level down
    if ops["tiff_list"], then ops["data_path"][0] / ops["tiff_list"] ONLY
    """
    froot = ops["data_path"]
    # use a user-specified list of tiffs
    if "tiff_list" in ops:
        fsall = []
        for tif in ops["tiff_list"]:
            fsall.append(os.path.join(froot[0], tif))
        ops["first_tiffs"] = np.zeros((len(fsall),), dtype="bool")
        ops["first_tiffs"][0] = True
        print("** Found %d tifs - converting to binary **" % (len(fsall)))
    else:
        if len(froot) == 1:
            if "subfolders" in ops and len(ops["subfolders"]) > 0:
                fold_list = []
                for folder_down in ops["subfolders"]:
                    fold = os.path.join(froot[0], folder_down)
                    fold_list.append(fold)
            else:
                fold_list = ops["data_path"]
        else:
            fold_list = froot
        fsall = []
        nfs = 0
        first_tiffs = []
        for k, fld in enumerate(fold_list):
            fs, ftiffs = list_files(fld, ops["look_one_level_down"],
                                    ["*.tif", "*.tiff", "*.TIF", "*.TIFF"])
            fsall.extend(fs)
            first_tiffs.extend(list(ftiffs))
        if len(fsall) == 0:
            print("Could not find any tiffs")
            raise Exception("no tiffs")
        else:
            ops["first_tiffs"] = np.array(first_tiffs).astype("bool")
            print("** Found %d tifs - converting to binary **" % (len(fsall)))
    return fsall, ops


def get_nd2_list(ops):
    """ make list of nd2 files to process
    if ops["look_one_level_down"], then all nd2"s in all folders + one level down
    """
    froot = ops["data_path"]
    fold_list = ops["data_path"]
    fsall = []
    nfs = 0
    first_tiffs = []
    for k, fld in enumerate(fold_list):
        fs, ftiffs = list_files(fld, ops["look_one_level_down"], ["*.nd2"])
        fsall.extend(fs)
        first_tiffs.extend(list(ftiffs))
    if len(fs) == 0:
        print("Could not find any nd2 files")
        raise Exception("no nd2s")
    else:
        ops["first_tiffs"] = np.array(first_tiffs).astype("bool")
        print("** Found %d nd2 files - converting to binary **" % (len(fsall)))
    return fsall, ops

def get_dcimg_list(ops):
    """ make list of dcimg files to process
        if ops["look_one_level_down"], then all dcimg"s in all folders + one level down
    """
    froot = ops["data_path"]
    fold_list = ops["data_path"]
    fsall = []
    nfs = 0
    first_tiffs = []
    for k, fld in enumerate(fold_list):
        fs, ftiffs = list_files(fld, ops["look_one_level_down"], ["*.dcimg"])
        fsall.extend(fs)
        first_tiffs.extend(list(ftiffs))
    if len(fs) == 0:
        print("Could not find any dcimg files")
        raise Exception("no dcimg")
    else:
        ops["first_tiffs"] = np.array(first_tiffs).astype("bool")
        print("** Found %d dcimg files - converting to binary **" % (len(fsall)))
    return fsall, ops

def find_files_open_binaries(ops1, ish5=False):
    """  finds tiffs or h5 files and opens binaries for writing

    Parameters
    ----------
    ops1 : list of dictionaries
        "keep_movie_raw", "data_path", "look_one_level_down", "reg_file"...

    Returns
    -------
        ops1 : list of dictionaries
            adds fields "filelist", "first_tiffs", opens binaries

    """

    reg_file = []
    reg_file_chan2 = []

    for ops in ops1:
        nchannels = ops["nchannels"]
        if "keep_movie_raw" in ops and ops["keep_movie_raw"]:
            reg_file.append(open(ops["raw_file"], "wb"))
            if nchannels > 1:
                reg_file_chan2.append(open(ops["raw_file_chan2"], "wb"))
        else:
            reg_file.append(open(ops["reg_file"], "wb"))
            if nchannels > 1:
                reg_file_chan2.append(open(ops["reg_file_chan2"], "wb"))

        if "input_format" in ops.keys():
            input_format = ops["input_format"]
        else:
            input_format = "tif"
    if ish5:
        input_format = "h5"
    print(input_format)
    if input_format == "h5":
        print(f"OPS1 h5py: {ops1[0]['h5py']}")
        if ops1[0]["h5py"]:
            fs = ops1[0]["h5py"]
            fs = [fs]
        else:
            if len(ops1[0]["data_path"]) > 0:
                fs, ops2 = get_h5_list(ops1[0])
                print("NOTE: using a list of h5 files:")
            # find h5"s
            else:
                raise Exception("No h5 files found")
        
    elif input_format == "sbx":
        # find sbx
        fs, ops2 = get_sbx_list(ops1[0])
        print("Scanbox files:")
        print("\n".join(fs))
    elif input_format == "nd2":
        # find nd2s
        fs, ops2 = get_nd2_list(ops1[0])
        print("Nikon files:")
        print("\n".join(fs))
    elif input_format == "movie":
        fs, ops2 = get_movie_list(ops1[0])
        print("Movie files:")
        print("\n".join(fs))
    elif input_format == "dcimg":
        # find dcimgs
        fs, ops2 = get_dcimg_list(ops1[0])
        print("DCAM image files:")
        print("\n".join(fs))
    else:
        # find tiffs
        fs, ops2 = get_tif_list(ops1[0])
        for ops in ops1:
            ops["first_tiffs"] = ops2["first_tiffs"]
            ops["frames_per_folder"] = np.zeros((ops2["first_tiffs"].sum(),), np.int32)
    for ops in ops1:
        ops["filelist"] = fs
    return ops1, fs, reg_file, reg_file_chan2


def init_ops(ops):
    """ initializes ops files for each plane in recording

    Parameters
    ----------
    ops : dictionary
        "nplanes", "save_path", "save_folder", "fast_disk", "nchannels", "keep_movie_raw"
        + (if mesoscope) "dy", "dx", "lines"

    Returns
    -------
        ops1 : list of dictionaries
            adds fields "save_path0", "reg_file"
            (depending on ops: "raw_file", "reg_file_chan2", "raw_file_chan2")

    """

    nplanes = ops["nplanes"]
    nchannels = ops["nchannels"]
    if "lines" in ops:
        lines = ops["lines"]
    if "iplane" in ops:
        iplane = ops["iplane"]
        #ops["nplanes"] = len(ops["lines"])
    ops1 = []
    if ("fast_disk" not in ops) or len(ops["fast_disk"]) == 0:
        ops["fast_disk"] = ops["save_path0"]
    fast_disk = ops["fast_disk"]
    # for mesoscope recording FOV locations
    if "dy" in ops and ops["dy"] != "":
        dy = ops["dy"]
        dx = ops["dx"]
    # compile ops into list across planes
    for j in range(0, nplanes):
        if len(ops["save_folder"]) > 0:
            ops["save_path"] = os.path.join(ops["save_path0"], ops["save_folder"],
                                            "plane%d" % j)
        else:
            ops["save_path"] = os.path.join(ops["save_path0"], "suite2p", "plane%d" % j)

        if ("fast_disk" not in ops) or len(ops["fast_disk"]) == 0:
            ops["fast_disk"] = ops["save_path0"].copy()
        fast_disk = os.path.join(ops["fast_disk"], "suite2p", "plane%d" % j)
        ops["ops_path"] = os.path.join(ops["save_path"], "ops.npy")
        ops["reg_file"] = os.path.join(fast_disk, "data.bin")
        if "keep_movie_raw" in ops and ops["keep_movie_raw"]:
            ops["raw_file"] = os.path.join(fast_disk, "data_raw.bin")
        if "lines" in ops:
            ops["lines"] = lines[j]
        if "iplane" in ops:
            ops["iplane"] = iplane[j]
        if nchannels > 1:
            ops["reg_file_chan2"] = os.path.join(fast_disk, "data_chan2.bin")
            if "keep_movie_raw" in ops and ops["keep_movie_raw"]:
                ops["raw_file_chan2"] = os.path.join(fast_disk, "data_chan2_raw.bin")
        if "dy" in ops and ops["dy"] != "":
            ops["dy"] = dy[j]
            ops["dx"] = dx[j]
        if not os.path.isdir(fast_disk):
            os.makedirs(fast_disk)
        if not os.path.isdir(ops["save_path"]):
            os.makedirs(ops["save_path"])
        ops1.append(ops.copy())
    return ops1


def get_suite2p_path(path: Path) -> Path:
    """Find the root `suite2p` folder in the `path` variable"""

    path = Path(path)  # In case `path` is a string

    # Cheap sanity check
    if "suite2p" in str(path):
        # Walk the folders in path backwards
        for path_idx in range(len(path.parts) - 1, 0, -1):
            if path.parts[path_idx] == "suite2p":
                new_path = Path(path.parts[0])
                for path_part in path.parts[1:path_idx + 1]:
                    new_path = new_path.joinpath(path_part)
                break
    else:
        raise FileNotFoundError("The `suite2p` folder was not found in path")
    return new_path


def frame_info_from_bruker_xml(xmlfile):
    """
    Reads bruker xml file and returns frame info.
    added by LP in sep 2022
    """
    xml_data    = et.parse(xmlfile)
    root        = xml_data.getroot()
    sequence    = root.findall('./Sequence')
    header      = root.findall('./PVStateShard/PVStateValue')
    # find starting position to use as default if recording is single_position
    # Note: Not sure if this works properly for multiple cycle recordings
    start_pos   = []
    for attr in header:
        if attr.attrib['key'] == 'positionCurrent':
            for subattr in attr.findall('./SubindexedValues'):
                for ipos in subattr.findall('./SubindexedValue'):
                    start_pos.append(float(ipos.get('value')))
    channel_num = []
    cycle_num   = []
    file_name   = []
    frame_time  = []
    pos         = []
    for [iCycle, cycle] in enumerate(sequence):

        # time stamp
        for frame in cycle.findall('./Frame'):
            frame_time.append(float(frame.attrib['relativeTime']))

        # cycle and channel info
        for frame in cycle.findall('./Frame/File'):
            file_name.append(frame.attrib['filename'])
            channel_num.append(int(frame.attrib['channel']))
            cycle_num.append(iCycle)

        # find x-y-z position for each frame
        for attr in cycle.findall('./Frame/PVStateShard/PVStateValue'):
            this_pos = []
            if attr.attrib['key'] == 'positionCurrent':
                for subattr in attr.findall('./SubindexedValues'):
                    for ipos in subattr.findall('./SubindexedValue'):
                        this_pos.append(float(ipos.get('value')))
                pos.append(this_pos)

    if not pos:
        for itimes in range(len(frame_time)):
            pos.append(start_pos)

    # define fov number based on the unique combination of x-y-z coordinates
    posa        = np.array(pos)
    unique_locs = np.unique(posa,axis=0)
    num_coord   = np.size(unique_locs,axis=1)
    num_fov     = np.size(unique_locs,axis=0)
    fov_id      = []

    for iFrame in range(len(pos)):
        for iFov in range(num_fov):
            if np.sum(posa[iFrame]==unique_locs[iFov]) == num_coord:
                fov_id.append(iFov)
                continue

    # create dictionary output
    frame_info = {
                 'xml_filename'     : xmlfile,                 \
                 'frame_file_names' : file_name,               \
                 'frame_times'      : np.array(frame_time),    \
                 'channel_ids'      : np.array(channel_num),   \
                 'fov_ids'          : np.array(fov_id),        \
                 'cycle_ids'        : np.array(cycle_num),     \
                 'fov_unique_pos'   : unique_locs,             \
                 'num_fov'          : num_fov,                 \
                 'num_channel'      : len(list(set(channel_num)))
                 }

    return frame_info

def infer_bruker_xml_filename(recpath):
    """
    Infers bruker xml file name based on path.
    added by LP in sep 2022
    """
    # print(recpath)
    # bruker xmls have the same name as their parent directory by default
    if recpath.find('/') == -1:
        if recpath.rfind('\\') == len(recpath)-1:
            recpath = recpath[:-1]
        xmlname = '{}.xml'.format(recpath[recpath.rfind('\\')+1:])
    else:
        if recpath.rfind('/') == len(recpath)-1:
            recpath = recpath[:-1]
        xmlname = '{}.xml'.format(recpath[recpath.rfind('/')+1:])
        
    # Return the full path to the file - PS 10/22
    xmlname =  os.path.join(recpath,xmlname)
    return xmlname
