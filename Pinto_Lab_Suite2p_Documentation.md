## Open Suite2p GUI
Open the GUI from a command line terminal.
~~~~
suite2p
~~~~
* This window should show up:
* <img width="1494" alt="Screenshot 2025-05-07 at 1 51 22 PM" src="https://github.com/user-attachments/assets/ddf49999-f048-4b93-bbee-841719ca0c50" />



## Run 2P session
* Go to `File/Run suite2p`
* <img width="1712" alt="Screenshot 2025-05-07 at 1 54 14 PM" src="https://github.com/user-attachments/assets/fcba866b-7354-4b2e-85a8-fb1255c3aa30" />
* For detecting axons, click `dendrites/axons` button. This will automatically load the ops parameters.
* Change `nplanes` based on the session.
* ROI detection is done with Cellpose model from: https://github.com/xzhang03/cellpose_GRIN_dendrite_models
    * Models are saved in `/suite2p/suite2p/models/`
    * GRINDen_Cy2000x.cpmodel works the best, GRINDen_Nu2000x.cpmodel is comparable. Other two don't work well.
* Click `Add directory to data_path`, and select the folder where the session tiff files are stored.
    * Local path recommended. Running directly from resfiles takes FOREVER.
    * Make sure folder name matches xml file name, otherwise will crash. Can just rename xml file if not match.
* Output will be saved in the data_path by default, use `Add save_path` button if you want to save it elsewhere.
* Click `RUN SUITE2P` button to start processing.
    * Pipeline register tiff files to a binary file first. If binary file already exist in destination, it will skip registration step (=save time).
    * So if ROI detection not ideal, no need to delete the output `suite2p` folder, just curate and rerun.
* GUI will show ROIs labelling after pipeline is done.
* <img width="1491" alt="Screenshot 2025-05-07 at 2 17 11 PM" src="https://github.com/user-attachments/assets/dba05780-08ef-4bf1-8548-dc6ccd807f7b" />
* Click `W` key or select `meanImg` in the background box to overlay ROIs on mean image.
* Set `classifier, cell prob=` to 0.
    * Current setting tend to classify ROIs as not cells. So switch them to cells by setting this threshold to 0.
* <img width="1494" alt="Screenshot 2025-05-07 at 2 18 08 PM" src="https://github.com/user-attachments/assets/dd4463ed-136b-41fa-837d-42e464391809" />
* Right click on selected ROIs will toggle them between cells/not cells.


## Load existing session
* Go to `File/Load processed data`, and choose the `stat.npy` file for the session.


