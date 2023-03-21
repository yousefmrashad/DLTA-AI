
import copy
from supervision.detection.core import Detections
import supervision as sv
from typing import List
from time import time
import sys
import torch
from mmdet.apis import inference_detector, init_detector , async_inference_detector
import cv2
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import splprep, splev
import json
import warnings
warnings.filterwarnings("ignore")


class models_inference():
    def __init__(self):
        self.annotating_models = {}


    def get_bbox(self,segmentation):
        x = []
        y = []
        for i in range(len(segmentation)):
            x.append(segmentation[i][0])
            y.append(segmentation[i][1])
        # get the bbox in xyxy format
        bbox = [min(x),min(y),max(x) ,max(y)]
        return bbox
    def interpolate_polygon(self , polygon, n_points):
        # interpolate polygon to get less points
        polygon = np.array(polygon)
        if len(polygon) < 20:
            return polygon
        x = polygon[:, 0]
        y = polygon[:, 1]
        tck, u = splprep([x, y], s=0, per=1)
        u_new = np.linspace(u.min(), u.max(), n_points)
        x_new, y_new = splev(u_new, tck, der=0)
        return np.array([x_new, y_new]).T

    # function to masks into polygons
    def mask_to_polygons(self , mask, n_points=20):
        # Find contours
        contours = cv2.findContours(
            mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)[0]
        # Convert contours to polygons
        polygon = []
        for contour in contours:
            contour = contour.flatten().tolist()
            # Remove last point if it is the same as the first
            if contour[-2:] == contour[:2]:
                contour = contour[:-2]
            polygon.append(contour)
        polygon = [(polygon[0][i], polygon[0][i + 1])
                   for i in np.arange(0, len(polygon[0]), 2)]
        polygon = self.interpolate_polygon(polygon, n_points)
        return polygon

    # experimental

    def full_points(bbox):
        return np.array([[bbox[0], bbox[1]], [bbox[0], bbox[3]], [bbox[2], bbox[3]], [bbox[2], bbox[1]]])

    def decode_file(self, img , model, classdict, threshold=0.3, img_array_flag=False , show_bbox_flag=False):

        if model.__class__.__name__ == "YOLO":
            results = model(img , conf=float(threshold))
            results = results[0]
            w , h = results.orig_img.shape[1] , results.orig_img.shape[0]
            segments = results.masks.segments
            detections = Detections(
                xyxy=results.boxes.xyxy.cpu().numpy(),
                confidence=results.boxes.conf.cpu().numpy(),
                class_id=results.boxes.cls.cpu().numpy().astype(int)
            )
            polygons = []
            result_dict = {}

            for seg_idx , segment in enumerate(segments):
                # segment is a array of points that make up the polygon of the mask and are set relative to the image size so we need to scale them to the image size
                for i in range(len(segment)):
                    segment[i][0] = segment[i][0] * w
                    segment[i][1] = segment[i][1] * h
                    
                    
                    
                # segment_points = self.interpolate_polygon(segment , 20)
                # if class is person we need to interpolate the polygon to get less points to make the polygon smaller
                if results.boxes.cls.cpu().numpy().astype(int)[seg_idx] == 0:
                    segment_points = self.interpolate_polygon(segment , 10)
                else :
                    segment_points = self.interpolate_polygon(segment , 20)
                
                
                # convert the segment_points to integer values
                segment_points = segment_points.astype(int)
                
                polygons.append(segment_points)

            # detection is a tuple of  (box, confidence, class_id, tracker_id)

            ind = 0
            res_list = []

            for detection in detections:

                result = {}
                result["class"] = classdict.get(int(detection[2]))
                result["confidence"] = str(detection[1])
                result["bbox"] = detection[0].astype(int)
                result["seg"] = polygons[ind]
                ind += 1
                if result["class"] == None:
                    continue
                if len(result["seg"]) < 3:
                    continue
                
                res_list.append(result)
            result_dict["results"] = res_list
            return result_dict




        if img_array_flag:
            results = inference_detector(model, img)
        else:
            results = inference_detector(model, plt.imread(img))
        # results = async_inference_detector(model, plt.imread(img_path))
        torch.cuda.empty_cache()







        results0 = []
        results1 = []
        for i in classdict.keys():
            results0.append(results[0][i])
            results1.append(results[1][i])
        
        self.annotating_models[model.__class__.__name__] = [results0 , results1]
        print(self.annotating_models.keys())

        # # if the length of the annotating_models is greater than 1 we need to merge the masks
        # if len(self.annotating_models.keys()) > 1:
        #     print("merging masks")
        #     results0,results1 =  self.merge_masks()

        #     assert len(results0) == len(results1)
        #     for i in range(len(results0)):
        #         assert len(results0[i]) == len(results1[i])

        result_dict = {}
        res_list = []

        #classdict = {0:"person", 1:"car", 2:"motorcycle", 3:"bus", 4:"truck"}
        self.classes_numbering = [keyno for keyno in classdict.keys()]
        for classno in range(len(results0)):
            for instance in range(len(results0[classno])):
                if float(results0[classno][instance][-1]) < float(threshold):
                    continue
                result = {}
                result["class"] = classdict.get(self.classes_numbering[classno])
                # Confidence
                result["confidence"] = str(results0[classno][instance][-1])
                if classno == 0:
                    result["seg"] = self.mask_to_polygons(
                        results1[classno][instance].astype(np.uint8) , 10)
                else :
                    result["seg"] = self.mask_to_polygons(
                        results1[classno][instance].astype(np.uint8) , 20)
                    
                    
                # result["bbox"] = self.get_bbox(result["seg"])
                if show_bbox_flag:
                    # result["bbox"] = full_points(result["bbox"]).tolist()
                    # points = full_points(result["bbox"])
                    # result["x1"] = points[0][0]
                    # result["y1"] = points[0][1]
                    # result["x2"] = points[1][0]
                    # result["y2"] = points[1][1]
                    # result["x3"] = points[2][0]
                    # result["y3"] = points[2][1]
                    # result["x4"] = points[3][0]
                    # result["y4"] = points[3][1]
                    x = 30  # nothing
                    
                    
                if result["class"] == None:
                    continue
                if len(result["seg"]) < 3:
                    continue
                res_list.append(result)

        result_dict["results"] = res_list
        return result_dict


    def merge_masks(self):
        result0 = []
        result1 = []

        # count the number of instances in each model
        counts = count_instances(self.annotating_models)
        # print the counts of each model
        for model in counts.keys():
            print("model {} has {} instances".format(model, counts[model]))

        classnos = []
        for model in self.annotating_models.keys():
            classnos.append(len(self.annotating_models[model][1]))
        merged_counts = 0
        # initialize the result list with the same number of classes as the model with the most classes
        for i in range(max(classnos)):
            result1.append([])
            result0.append([])

        # deep copy the annotating_models dict to pop all the masks we have merged (try delete it for future optimisation)
        annotating_models_copy = copy.deepcopy(self.annotating_models)
        # merge masks of the same class
        for model in self.annotating_models.keys():
            for classno in range(len(self.annotating_models[model][1])):
                # check if an instance exists in the model in this class
                if len(self.annotating_models[model][1][classno]) > 0:
                    for instance in range(len(self.annotating_models[model][1][classno])):
                        for model2 in self.annotating_models.keys():
                            if model != model2 and (model2 > model):
                                #print(type(annotating_models_copy[model][0][classno]),type(annotating_models_copy[model2][0][classno]))
                                # check if the class exists in the other model
                                if classno in range(len(self.annotating_models[model2][1])):
                                    # check if an instance exists in the other model
                                    if len(self.annotating_models[model2][1][classno]) > 0:
                                        for instance2 in range(len(self.annotating_models[model2][1][classno])):
                                            # get the intersection percentage of the two masks
                                            intersection = np.logical_and(self.annotating_models[model][1][classno][instance] , self.annotating_models[model2][1][classno][instance2])
                                            intersection = np.sum(intersection)
                                            union = np.logical_or(self.annotating_models[model][1][classno][instance] , self.annotating_models[model2][1][classno][instance2])
                                            union = np.sum(union)
                                            iou = intersection / union
                                            #print('iou of class ' + str(classno) + ' instance ' + str(instance) + ' and instance ' + str(instance2) + ' is ' + str(iou))
                                            if iou > 0.5:
                                                #print('merging masks of class ' + str(classno) + ' instance ' + str(instance) + ' and instance ' + str(instance2) + ' of models ' + model + ' and ' + model2)
                                                merged_counts += 1
                                                # store the merged mask in result1
                                                result1[classno].append(np.logical_or(self.annotating_models[model][1][classno][instance] , self.annotating_models[model2][1][classno][instance2]))
                                                # merge their bboxes and store the result in result0
                                                bbox1 = self.annotating_models[model][0][classno][instance]
                                                bbox2 = self.annotating_models[model2][0][classno][instance2]
                                                bbox = [min(bbox1[0], bbox2[0]), min(bbox1[1], bbox2[1]), max(bbox1[2], bbox2[2]), max(bbox1[3], bbox2[3]), ((bbox1[4] + bbox2[4]) / 2)]
                                                result0[classno].append(bbox)
                                                # remove the mask from both models
                                                annotating_models_copy[model][1][classno][instance] = None
                                                annotating_models_copy[model2][1][classno][instance2] = None
                                                annotating_models_copy[model][0][classno][instance] = None
                                                annotating_models_copy[model2][0][classno][instance2] = None
                                                # continue to the next instance of the first model
                                                break
                                                

        counts_here = {}                        
        # add the remaining masks to the result
        for model in annotating_models_copy.keys():
            counts_here[model] = 0
            for classno in range(len(annotating_models_copy[model][1])):
                for instance in range(len(annotating_models_copy[model][1][classno])):
                    if annotating_models_copy[model][1][classno][instance] is not None:
                        counts_here[model] += 1
                        #print('adding mask of class ' + str(classno) + ' instance ' + str(instance) + ' of model ' + model)
                        result1[classno].append(annotating_models_copy[model][1][classno][instance])
                        result0[classno].append(annotating_models_copy[model][0][classno][instance])
        # clear the annotating_models and add the result to it
        self.annotating_models = {}
        self.annotating_models["merged"] = [result0 , result1]
        for model in counts_here.keys():
            print("model {} has {} instances".format(model, counts_here[model]))
        print("merged {} instances".format(merged_counts))
        return result0 , result1
    

                                
# result will have ---> bbox , confidence , class_id , tracker_id , segment
# result of the detection phase only should be (bbox , confidence , class_id , segment)
def count_instances(annotating_models):
    # separate the counts for each model
    counts = {}
    for model in annotating_models.keys():
        counts[model] = 0
        for classno in range(len(annotating_models[model][1])):
            counts[model] += len(annotating_models[model][1][classno])
    return counts