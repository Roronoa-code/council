# Reproducible computational frame analysis

All **1,209 frames** of the supplied 40.3-second, 30 fps, 576 × 1024 video were decoded. `video-frame-index.csv.meta.json` records the source SHA-256 and algorithm. The complete compressed numerical CSV ledger is supplied separately with the build-session artifacts; this public repository keeps the reproducible utility, metadata and visual study. The original video, audio and image frames are not redistributed.

This second pass uses full-resolution grayscale frames and the mean absolute luminance difference from the preceding frame. It is separate from the initial reduced-image transition scan used to select contact sheets. Numerical transition scores are not a transcript and do not prove that every nearly identical frame was separately interpreted by a person. The actual concept/caption observations are in `00-video-analysis.md`.

To regenerate the ledger from the original video, install the optional `opencv-python` research dependency, then run:

```sh
python tools/index_video.py path/to/video.mp4 --out video-frame-index.csv.gz
```

Read that output using the Python standard library:

```sh
python -c "import gzip; print(gzip.open('video-frame-index.csv.gz', 'rt').read())"
```

No OCR was used. Visual inspection used timestamped contact sheets and enlarged cut-adjacent frames. The clip does not provide its implementation source, independently verified customer outcomes, or a tested demonstration that a council improves decisions.
