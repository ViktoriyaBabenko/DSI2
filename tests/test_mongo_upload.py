import sys,os
import numpy as np
import paths
from dsi2.database.local_data import get_local_data
test_input_data = paths.test_input_data
test_output_data = paths.test_output_data

from scipy.stats import itemfreq
import cPickle as pickle

import pymongo
from bson.binary import Binary

import pytest

@pytest.fixture(scope="module")
def db():
    connection = pymongo.MongoClient()
    return connection.dsi2_test

@pytest.fixture(scope="module")
def local_scans():
    return get_local_data(test_output_data + "/example_data.json",
                          pkl_dir=test_output_data)

def test_mongo_connection(db):
    # Ensure there is an index for fast querying
    # TODO: How should the compound indexes be ordered? What is most efficient?

    db.streamlines.ensure_index([("scan_id",pymongo.ASCENDING),("sl_id",pymongo.ASCENDING)])
    db.coordinates.ensure_index([("scan_id",pymongo.ASCENDING),("ijk",pymongo.ASCENDING)])
    
    db.connections.ensure_index([("con_id",pymongo.ASCENDING),("scan_id",pymongo.ASCENDING),("atlas_id",pymongo.ASCENDING)])
    db.streamline_labels.ensure_index([("scan_id",pymongo.ASCENDING),("atlas_id",pymongo.ASCENDING)])
    
    db.atlases.ensure_index([("name",pymongo.ASCENDING)])
    
    db.scans.ensure_index([("scan_id",pymongo.ASCENDING),("subject_id",pymongo.ASCENDING)])
    
def test_insertion(db,local_scans):
    for sc in local_scans:
        # load the TrackDatasets one at a time
        trackds = sc.get_track_dataset()
    
        atlases = []
        for label in trackds.properties.track_label_items:
            atlas_labels = label.load_array()
    
            # Does this atlas already exist? If not, add it to the collection.
            atlas = None
            result = db.atlases.find( { "name": label.name, "parameters": label.parameters } )
            if result.count() != 0:
                atlas = result[0]["_id"]
            else:
                atlas = db.atlases.insert( { "name": label.name, "parameters": label.parameters } )
    
            atlases.append(atlas)
            
            inserts = []
            inserts.append(
                    {
                        "scan_id": sc.scan_id,
                        "atlas_id": atlas,
                        "con_ids": list(map(int,atlas_labels))
                    }
                    )
    
            db.streamline_labels.insert(inserts)
    
            #trackds.set_connections(atlas_labels)
    
            inserts = []
            con_ids = set(atlas_labels)
            print "Building connections collection for %s %d..." % (label.name, label.parameters["scale"])
            for con_id in con_ids:
                sl_ids = list(map(int,np.where(atlas_labels == con_id)[0]))
                inserts.append(
                        {
                            "con_id":"%d" % con_id,
                            "scan_id":sc.scan_id,
                            "atlas_id":atlas,
                            "sl_ids":sl_ids
                        }
                        )
    
            db.connections.insert(inserts)
    
            print "done."
    
    
    #    print "Building connections collection..."
    #    # insert a document for each coordinate
    #    total_n = len(trackds.tracks_at_ijk.keys())
    #    n=0
    #    print "total", total_n
    #    inserts = []
    #    for coord,indices in trackds.tracks_at_ijk.iteritems():
    #        connections = trackds.connections[np.array(list(indices))]
    #        freqs = itemfreq(connections)
    #        inserts.append(
    #            {
    #             "ijk":"(%d, %d, %d)" % tuple(map(int,coord)),
    #             "scan_id":sc.scan_id,
    #             "con":[{"con":"c%d"%k, "count":int(v)} for k,v in freqs]
    #            }
    #          )
    #        n += 1
    #    db.connections.insert(inserts)
    #    print "done."
    
    
        print "Building streamline collection..."
        inserts = []
        for ntrk, trk in enumerate(trackds.tracks):
            if len(inserts) >= 1000:
                db.streamlines.insert(inserts)
                inserts = []
    
            inserts.append(
                {
                  "scan_id":sc.scan_id,
                  "sl_id": ntrk,
                  "data":Binary(pickle.dumps(trk,protocol=2))
                 }
            )
        db.streamlines.insert(inserts)  
    
        print "done."
    
        inserts = []
        print "Building coordinate collection..."
        for coord,indices in trackds.tracks_at_ijk.iteritems():
            inserts.append(
               {
                "ijk":"(%d, %d, %d)" % tuple(map(int,coord)),
                "scan_id":sc.scan_id,
                "sl_id":list(map(int,indices))
               }
              )
        db.coordinates.insert(inserts)
        print "done."
    
        # TODO: add more scan metadata
        inserts = []
        print "Building scan collection..."
        inserts.append(
                {
                    "scan_id":sc.scan_id,
                    "subject_id":sc.subject_id,
                    "gender":sc.scan_gender,
                    "age":sc.scan_age,
                    "study":sc.study,
                    "group":sc.scan_group,
                    "smoothing":sc.smoothing,
                    "cutoff_angle":sc.cutoff_angle,
                    "qa_threshold":sc.qa_threshold,
                    "gfa_threshold":sc.gfa_threshold,
                    "length_min":sc.length_min,
                    "length_max":sc.length_max,
                    "institution":sc.institution,
                    "reconstruction":sc.reconstruction,
                    "scanner":sc.scanner,
                    "n_directions":sc.n_directions,
                    "max_b_value":sc.max_b_value,
                    "bvals":sc.bvals,
                    "bvecs":sc.bvecs,
                    "label":sc.label,
                    "trk_space":sc.trk_space,
                    "atlases":list(set(atlases)),
                    "sls":len(trackds.tracks),
                    "header":Binary(pickle.dumps(trackds.header,protocol=2)),
                }
                )
        db.scans.insert(inserts)
        print "done."
    
