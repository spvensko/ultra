#!/bin/bash

set -e
if [ $# -ne 1 ]; then
        echo "Usage: `basename $0` <installation_path> "
        exit -1
fi
path=$1
mkdir -p $path

# create temporary installation folder
mkdir -p "temp_install_ultra"
cd "temp_install_ultra"

echo
echo "I'm in temporary folder" $PWD
echo 

# Create and activate a new environment called ultra
echo "SETTING UP CONDA ENVIRONMENT"
echo

# Install uLTRA
echo
echo "INSTALLING ULTRA"
echo
pip install ultra-bioinformatics


# Install MEM finder namfinder 
echo
echo "INSTALLING NAMFINDER"
echo
installed_namfinder=false
if ! command -v namfinder &> /dev/null
then
    conda install -c bioconda namfinder
fi

# Install aligner minimap2
echo
echo "INSTALLING MINIMAP2"
echo

installed_mm2=false
if ! command -v minimap2 &> /dev/null
then
    conda install -c bioconda minimap2
fi


echo
echo "TESTING INSTALLATION OF ULTRA"
echo

cd ..
uLTRA pipeline $PWD/test/SIRV_genes.fasta $PWD/test/SIRV_genes_C_170612a.gtf $PWD/test/reads.fa temp_install_ultra/

echo
echo "INSTALLATION WORKED"
echo


rm -rf "temp_install_ultra"

echo
echo "FINISHED INSTALLATION"
echo
if [ "$installed_mm2" = true ] ; then
    echo "I have put minimap2 in:" $path " please make sure that this folder is in your path, or move minimap2 to your path"
fi

if [ "$installed_namfinder" = true ] ; then
    echo "I have put namfinder in:" $path " please make sure that this folder is in your path, or move slaMEM to your path"
fi


echo "Please activate the environment as 'conda activate ultra' before running uLTRA."
echo
