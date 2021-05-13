#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 10 13:20:12 2021

@author: jackreid
"""

import ee
import folium
from datetime import datetime as dt
from datetime import timedelta
import pandas as pd
import numpy as np
from dateutil.parser import parse
import gdal, os
import subprocess
import time

# =============================================================================
# %% 1 - DISPLAYING / FOLIUM UTILITIES             
# =============================================================================

def add_ee_layer(self, ee_image_object, vis_params, name, show=True, opacity=1, min_zoom=0):
    """ From s2cloudless"""
    """DEFINE A METHOD FOR DISPLAYING EARTH ENGINE IMAGE TILES TO A FOLIUM MAP
    
    Args:
        ee_image_object: ee.Image to be mapped
        vis_params: Dictionary of GEE visualization parameters
        name: String, layer label to be shown in the legend
        show: Boolean, defines whether to show layer by default on map
        opacity: float, 0-1, defines opacity of layer, 1 is opaque, 0 is transparent
        min_zoom: ???
    
    Returns:
        N/A
    """
    
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr='Map Data &copy; <a href="https://earthengine.google.com/">Google Earth Engine</a>',
        name=name,
        show=show,
        opacity=opacity,
        min_zoom=min_zoom,
        overlay=True,
        control=True
        ).add_to(self)
    
   
# =============================================================================
# %% 2 - GEE DATA PROCESSING UTILITIES             
# =============================================================================

# Define a function to transfer feature properties to a dictionary.
def fc_to_dict(fc):
    """DEFINE A FUNCTION TO TRANSFER FEATURE PROPERITIES TO A DICTIONARY
    
    Args:
        fc: ee.FeatureCollection
    
    Returns:
        ee.Dictionary with properties of each feature
    """
    
    prop_names = fc.first().propertyNames()
    prop_lists = fc.reduceColumns(
        reducer=ee.Reducer.toList().repeat(prop_names.size()),
        selectors=prop_names).get('list')
  
    return ee.Dictionary.fromLists(prop_names, prop_lists)



def time_series_regions_reducer(imgcol, 
                                bands, 
                                geometry, 
                                FeatureID='BAIRRO', 
                                timescale = 'system:time_start', 
                                timeunit = 'integer',
                                stats='median', 
                                scale=470):
    
    """DEVELOP A DATAFRAME FROM A REGIONS REDUCER OF AN IMAGE COLLECTION
    
    Args:
        imgcol: ee.ImageCollection to be reduced
        bands: List of strings, bands of interest to be reduced
        geometry: ee.FeatureCollection, regions to reduce over
        FeatureID: str, property of each feature geometry to use as column labels in output
        timescale: str, property of each image in imgcol to use as the designation of time
        timeunit: str, format of timescale. If 'date', function will try to convert to datetime
        stats: str, type of reducer to be performed
        scale: int, spatial scale to reduce at
    
    Returns:
        df: Dataframe based on reduced statistics with (FeatureIDs + timescale) as columns and rows for each image
    """
    
    #Check for reducer type
    if stats == 'mean':
        fun = ee.Reducer.mean()
    elif stats == 'median':
        fun = ee.Reducer.median()
    elif stats == 'max':
        fun = ee.Reducer.max()
    elif stats == 'min':
        fun = ee.Reducer.min()
    
    #Function for flattening ee.Lists generated  by Reducer.toList in particular way
    def list_simplify(entry):
        val = ee.List(entry).get(0)
        return val

    #Mapping function to conduct reduction on each image
    def run_reduce(img):
        feat_reduce = (img.select(bands).reduceRegions(
                    collection = geometry,
                    reducer = fun,
                    scale = scale))
        
        #Convert reduction to lists
        data_list_bairro = ee.List(feat_reduce.reduceColumns(ee.Reducer.toList(1), [FeatureID]).get('list'))
        data_list_median = ee.List(feat_reduce.reduceColumns(ee.Reducer.toList(1), [stats]).get('list'))
        data_list_bairro_simple = ee.List(data_list_bairro.map(list_simplify))
        data_list_median_simple = ee.List(data_list_median.map(list_simplify))
        
        #Replace null values with -999999
        data_list_median_simple = ee.Algorithms.If(data_list_median_simple.length().lt(ee.List(data_list_bairro_simple).length())
                                                   ,ee.List.repeat(-999999,data_list_bairro_simple.length()),
                                                   data_list_median_simple)
    
        #Convert from lists to dictionary
        data_dict = ee.Dictionary.fromLists(data_list_bairro_simple, data_list_median_simple)
    
        #Return original image with reduced statistics added as properties
        return img.set(data_dict)
    
    #Run reduction on imgcol
    reduced_collection = imgcol.map(run_reduce)
    
    #Generate lists of dataframe column names
    bairros_list_temp = ee.List(geometry.reduceColumns(ee.Reducer.toList(1), [FeatureID]).get('list'))
    bairros_list = bairros_list_temp.map(list_simplify)
    bairros_list_complete = bairros_list.add('system:time_start')
    
    #Extract reduced statistics from image collection into list
    nested_list = reduced_collection.reduceColumns(ee.Reducer.toList(bairros_list_complete.length()), bairros_list_complete).values().get(0)
    
    #Convert reduced statistics into dataframe and convert null values to NaN
    df = (pd.DataFrame(nested_list.getInfo(), columns=list(bairros_list_complete.getInfo())).replace(-999999,np.nan))
    
    #Convert timeunit if appropriate
    if timeunit == 'date':
        for index in df.index.values.tolist():
            df.at[index,'system:time_start'] = dt.fromtimestamp(df.at[index,'system:time_start'] / 1000)
    
    return df

# =============================================================================
# %% 3 - GENERAL GEE UPLOAD AND IMPORT       
# =============================================================================

def format_dir_nospace(dirpath):
    """ESCAPE SPACES IN DIRECTORY PATH
    
    Args:
        dirpath: Str, directory path to be corrected
    
    Returns:
        dirpath: Str, directory path with escaped spaces and appended backslash
    """
    
    dirpath = dirpath.replace(" ", "\ ")
    if dirpath[-1] != '/':
        dirpath = dirpath + '/'
    return dirpath

def format_dir_space(dirpath):
    """REMOVE ESCAPED SPACES FROM DIRECTORY PATH
    
    Args:
        dirpath: Str, directory path to be corrected
    
    Returns:
        dirpath: Str, directory path with plain spaces and appended backslash
    """
    
    dirpath = dirpath.replace("\ ", " ")
    if dirpath[-1] != '/':
        dirpath = dirpath + '/'
    return dirpath

def gcloud_upload(geotiffFolder, bucket):
    """UPLOAD BATCH OF GEOTIFF IMAGES TO GOOGLE CLOUD STORAGE
    
    Args:
        geotiffFolder: Str, path of directory containing geotiff images to be uploaded
        bucket: Str, name of Google Cloud bucket to place images in
    
    Returns:
        N/A
    """
    
    #Format directory path and generate list of files to be converted
    geotiffFolder = format_dir_nospace(geotiffFolder)
    filenames = subprocess.getoutput('find ' + geotiffFolder + " -name '*.tif'")
    totalLength = len(filenames.splitlines())
    index = 0
    
    #Iterate through and upload each image
    for file in filenames.splitlines():
        subprocess.call(['gsutil', '-m', 'cp', file, 'gs://' + bucket + '/'])
        index+=1
        percentageComplete = index/totalLength*100
        print(str(percentageComplete) + "% Complete")

# =============================================================================
# %% 4 - BLACK MARBLE NIGHTLIGHTS CONVERSION AND IMPORT           
# =============================================================================

def bm_hd5_to_geotiff(hd5Folder, geotiffFolder):
    """ Based on NASA's Black Marble OpenHDF5.py"""
    """CONVERT A BATCH OF HD5 BLACK MARBLE IMAGES TO GEOTIFF
    
    Args:
        hd5Folder: Str, path of directory containing hd5 images to be converted
        geotiffFolder: Str, path of target directory to place geotiffs
    
    Returns:
        N/A
    """
    
    #Check if suitable temprary directory is available, create one if not
    temp_check = os.path.join(os.getcwd(), 'temp_dir_for_hd5')
    if os.path.exists(temp_check):
        if os.path.isdir(temp_check):
            tempFolder = temp_check
        else:
            tempFolder = os.path.join(temp_check, str(round(time.time())))
            os.mkdir(tempFolder)
    else:
        os.mkdir(temp_check)
        tempFolder = temp_check
        
    #Format relevant directory paths
    geotiffFolder = format_dir_nospace(geotiffFolder)
    tempFolder = format_dir_nospace(tempFolder)
    tempFolder_space = format_dir_space(tempFolder)
    
    ## List input raster files
    os.chdir(hd5Folder)
    rasterFiles = os.listdir(os.getcwd())
    
    #Get File Name Prefix
    index = 1
    totalLength = len(rasterFiles)
    for file in rasterFiles:
    
        rasterFilePre = file[:-3]
        print(rasterFilePre)
    
        fileExtension = "_BBOX.tif"
        
        ## Open HDF file
        hdflayer = gdal.Open(file, gdal.GA_ReadOnly)
        # # print (hdflayer.GetSubDatasets())
        
        # Open raster layer
        for layer in hdflayer.GetSubDatasets():
            
            #hdflayer.GetSubDatasets()[0][0] - for first layer
            #hdflayer.GetSubDatasets()[1][0] - for second layer ...etc
            subhdflayer = layer[0]
            rlayer = gdal.Open(subhdflayer, gdal.GA_ReadOnly)
        
            #Subset the Long Name and Generate Name of Temporary Files
            outputName = subhdflayer[92:]
            outputNameNoSpace = outputName.strip().replace(" ","_").replace("/","_")
            outputNameFinal = rasterFilePre + outputNameNoSpace + fileExtension
            outputFolder = tempFolder_space            
            outputRaster = outputFolder + outputNameFinal
            
            #Collect bounding box coordinates
            HorizontalTileNumber = int(rlayer.GetMetadata_Dict()["HorizontalTileNumber"])
            VerticalTileNumber = int(rlayer.GetMetadata_Dict()["VerticalTileNumber"])
            WestBoundCoord = (10*HorizontalTileNumber) - 180
            NorthBoundCoord = 90-(10*VerticalTileNumber)
            EastBoundCoord = WestBoundCoord + 10
            SouthBoundCoord = NorthBoundCoord - 10
            
            #Set projection
            EPSG = "-a_srs EPSG:4326" #WGS84
            translateOptionText = EPSG+" -a_ullr " + str(WestBoundCoord) + " " + str(NorthBoundCoord) + " " + str(EastBoundCoord) + " " + str(SouthBoundCoord)
            translateoptions = gdal.TranslateOptions(gdal.ParseCommandLine(translateOptionText))
            
            #Generate layers as temporary raster files
            gdal.Translate(outputRaster,rlayer, options=translateoptions)
            
        #Combine temporary rasters into geotiff
        filepre = rasterFilePre
        commandtext = 'gdal_merge.py -separate -o ' + geotiffFolder + filepre + '.tif ' + tempFolder + filepre + '*tif'
        subprocess.call(commandtext, shell=True)
        
        #Remove temporary raster riles
        subprocess.call('rm ' + tempFolder + filepre + '*tif', shell=True)
        
        #Report on progress
        index+=1
        percentageComplete = index/totalLength*100
        print(str(percentageComplete) + "% Complete")
        

def bmA2_gee_import(bucket, destination):
    """IMPORT A COLLECTION OF VNP46A2 GEOTIFFS FROM GOOGLE CLOUD STORAGE INTO 
        A GOOGLE EARTH ENGINE IMAGE COLLECTION
    
    Args:
        bucket: Str, name of Google Cloud Storage bucket containing geotiff images to be imported
        destination: Str, name of Google Earth Engine Image Collection to place images in

    Returns:
        N/A
    """

    #Generate list of files to be imported
    filenames_raw = subprocess.getoutput('gsutil ls gs://' + bucket)
    filenames_split = [x[5:] for x in filenames_raw.split()]
    totalLength = len(filenames_split)

    #Initiate null list to track asset id names to avoid overwrites
    asset_list = []
    
    #Iterate through each filename
    index = 0
    for file in filenames_split:
    # for file in filenamelist.split()[1:2]:
        
        #Identify base name of the file and the date of image to serve as central component of asset id        
        base_name = os.path.basename(os.path.normpath(file))
        sep = '.'
        date_name = base_name.split(sep)[1]
        year = date_name[1:5]
        daynum = date_name[5:8]
        prod_name = base_name.split(sep)[4]
        hour = prod_name[7:9]
        minute = prod_name[9:11]
        second = prod_name[11:13]
        fulldate = dt(int(year), 1, 1) + timedelta(int(daynum) - 1)
        day = '{:02d}'.format(fulldate.day)
        month = '{:02d}'.format(fulldate.month)
        vdate = year + '-' + month + '-' + day + 'T' + hour + ':' + minute + ':' + second
        timestring = ' --time_start=' + vdate

        #Concatante asset id name
        assetname = base_name[-17:-4]
                
        #Check if asset id already exists, generate number to append if so
        assetflag = 0
        for i in asset_list: 
            if(i == assetname):
                assetflag += 1
        asset_list.append(assetname)
        if assetflag != 0:
            assetname = assetname + '_' + str(assetflag)
        
        #Generate command sequence for importing the asset
        assetstring = ' --asset_id=users/' + destination + '/' + assetname
        bucketstring = ' gs://' + bucket + '/' + base_name
        commandstring = 'earthengine upload image' + assetstring + timestring + bucketstring
        print(commandstring)
        
        #Run the command sequence
        subprocess.call(commandstring,
                        shell=True)
        
        index+=1
        percentageComplete = index/totalLength*100
        print(str(percentageComplete) + "% Complete")
