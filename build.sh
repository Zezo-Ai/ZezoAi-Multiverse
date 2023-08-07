#!/usr/bin/env sh

git submodule update --init

SRC_DIR="$(dirname $0)/src"

# Specify the folder path to create
BUILD_DIR="$(dirname $0)/build"

# Build USD

# Check if the folder already exists
USD_BUILD_DIR=$BUILD_DIR/USD
USD_SRC_DIR=$SRC_DIR/USD
if [ ! -d "$USD_BUILD_DIR" ]; then
    # Create the folder if it doesn't exist
    mkdir -p "$USD_BUILD_DIR"
    echo "Folder created: $USD_BUILD_DIR"
else
    echo "Folder already exists: $USD_BUILD_DIR"
fi

(python3 $USD_SRC_DIR/build_scripts/build_usd.py $USD_BUILD_DIR)

# Build MuJoCo

# Check if the folder already exists
MUJOCO_BUILD_DIR=$BUILD_DIR/mujoco
MUJOCO_SRC_DIR=$SRC_DIR/mujoco
if [ ! -d "$MUJOCO_BUILD_DIR" ]; then
    # Create the folder if it doesn't exist
    mkdir -p "$MUJOCO_BUILD_DIR"
    echo "Folder created: $MUJOCO_BUILD_DIR"
else
    echo "Folder already exists: $MUJOCO_BUILD_DIR"
fi

cmake -S $MUJOCO_SRC_DIR -B $MUJOCO_BUILD_DIR
(cd $MUJOCO_BUILD_DIR && make)

# Build blender

# Check if the folder already exists
BLENDER_BUILD_DIR=$BUILD_DIR/blender
BLENDER_SRC_DIR=$SRC_DIR/blender-git
if [ ! -d "$BLENDER_BUILD_DIR" ]; then
    # Create the folder if it doesn't exist
    mkdir -p "$BLENDER_BUILD_DIR"
    echo "Folder created: $BLENDER_BUILD_DIR"
else
    echo "Folder already exists: $BLENDER_BUILD_DIR"
fi

if [ ! -d "$BLENDER_SRC_DIR/lib" ]; then
    (cd $BLENDER_SRC_DIR; mkdir lib; cd lib; svn checkout https://svn.blender.org/svnroot/bf-blender/trunk/lib/linux_x86_64_glibc_228)
    (cd $BLENDER_SRC_DIR/blender; make update)
fi

(cd $BLENDER_SRC_DIR/blender && make BUILD_DIR=$BLENDER_BUILD_DIR/build_linux)
(cd $BLENDER_SRC_DIR/blender && make bpy BUILD_DIR=$BLENDER_BUILD_DIR/build_linux_bpy)