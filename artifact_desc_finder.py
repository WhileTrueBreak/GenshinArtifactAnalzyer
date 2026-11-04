import os

import cv2
import numpy as np

# folder = 'res/desc_bank'
# images = []
# for i, filename in enumerate(sorted(os.listdir(folder))):
#     path = os.path.join(folder, filename)
#     image = cv2.imread(path)
#     images.append(image[:283,:])
# images = np.array(images)

# images = images.astype(np.float32)
# median = np.median(images, axis=0)
# consistent = np.abs(images - median) <= 3
# mask = np.mean(np.all(consistent, axis=3), axis=0) >= 0.95
# mask = cv2.erode(mask.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
# cv2.imwrite('res/desc_template_mask.png', mask.astype(np.uint8) * 255)
# cv2.imwrite('res/desc_template.png', median.astype(np.uint8))

def calc_hist_cdf(image):
    hist = cv2.calcHist([image], [0], None, [256], [0, 256])
    cdf = hist.cumsum()
    cdf = cdf / cdf[-1]
    return cdf

def equalize_from_template(image, cdf):
    lut = np.clip(np.round(cdf * 255), 0, 255).astype(np.uint8)
    return cv2.LUT(image, lut)

DESC_TEMPLATE = cv2.imread('res/desc_template.png')
DESC_TEMPLATE_LAB = cv2.cvtColor(DESC_TEMPLATE, cv2.COLOR_BGR2LAB)
DESC_TEMPLATE_MASK = cv2.imread('res/desc_template_mask.png')
DESC_TEMPLATE_HIST_CDF = np.zeros((256,3))
DESC_TEMPLATE_HIST_CDF[:,0] = calc_hist_cdf(DESC_TEMPLATE_LAB[:,:,0])
DESC_TEMPLATE_HIST_CDF[:,1] = calc_hist_cdf(DESC_TEMPLATE_LAB[:,:,1])
DESC_TEMPLATE_HIST_CDF[:,2] = calc_hist_cdf(DESC_TEMPLATE_LAB[:,:,2])
DESC_TEMPLATE_LAB[:,:,0] = equalize_from_template(DESC_TEMPLATE_LAB[:,:,0], DESC_TEMPLATE_HIST_CDF[:,0])
DESC_TEMPLATE_LAB[:,:,1] = equalize_from_template(DESC_TEMPLATE_LAB[:,:,1], DESC_TEMPLATE_HIST_CDF[:,1])
DESC_TEMPLATE_LAB[:,:,2] = equalize_from_template(DESC_TEMPLATE_LAB[:,:,2], DESC_TEMPLATE_HIST_CDF[:,2])

def find_template(image, template, mask):
    mask = (mask > 0).astype(np.uint8) * 255

    result = cv2.matchTemplate(image[:, :, 0],template[:, :, 0],cv2.TM_CCORR_NORMED,mask=mask[:, :, 0])

    valid = np.isfinite(result)
    if not np.any(valid):
        return None
    result_clean = np.where(valid, result, -1)
    result_vis = np.nan_to_num(result, nan=0, posinf=0, neginf=0)
    result_vis = np.clip(result_vis * 255, 0, 255).astype(np.uint8)
    cv2.imwrite('crops/match_result.png', result_vis)

    _, max_val, _, max_loc = cv2.minMaxLoc(result_clean)

    valid_values = result[valid]
    mean = np.mean(valid_values)
    std = np.std(valid_values)

    z_score = (max_val - mean) / (std + 1e-8)

    h, w = template.shape[:2]

    return (
        max_loc,
        (max_loc[0] + w, max_loc[1] + h),
        max_val,
        z_score
    )

def crop_desc(image):
    h,_,_ = DESC_TEMPLATE_LAB.shape
    image_lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)[:-(283-h),:]

    image_lab[:,:,0] = equalize_from_template(image_lab[:,:,0],DESC_TEMPLATE_HIST_CDF[:,0])
    image_lab[:,:,1] = equalize_from_template(image_lab[:,:,1],DESC_TEMPLATE_HIST_CDF[:,1])
    image_lab[:,:,2] = equalize_from_template(image_lab[:,:,2],DESC_TEMPLATE_HIST_CDF[:,2])
    
    top_left, _, confidence, z_score = find_template(image_lab, DESC_TEMPLATE_LAB, DESC_TEMPLATE_MASK)
    cropped = image[top_left[1]:top_left[1]+839,top_left[0]:top_left[0]+492]
    return cropped, confidence, z_score

if __name__ == '__main__':
    folder = 'screens'
    for i, filename in enumerate(sorted(os.listdir(folder))):
        print(f'{i}')
        path = os.path.join(folder, filename)
        image = cv2.imread(path).cvtColor(cv2.COLOR_BGR2RGB)
        cropped, conf, z_score = crop_desc(image)
        if conf < 0.9: continue
        print(f'Conf: {conf}')
        print(f'Z Score: {z_score}')
        cv2.imwrite(f'crops/result_{i}.png', cropped)
        cv2.imwrite(f'crops/result_{i}_.png', image)