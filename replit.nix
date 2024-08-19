{ pkgs }: {
  deps = [
    pkgs.ffmpeg.bin
  ];
  env = {
    LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
      pkgs.libxss-dev
      pkgs.libopus
    ];
  };
}