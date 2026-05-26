;; Auto-generated. Do not edit!


(when (boundp 'head_posture_module::HeadPosture)
  (if (not (find-package "HEAD_POSTURE_MODULE"))
    (make-package "HEAD_POSTURE_MODULE"))
  (shadow 'HeadPosture (find-package "HEAD_POSTURE_MODULE")))
(unless (find-package "HEAD_POSTURE_MODULE::HEADPOSTURE")
  (make-package "HEAD_POSTURE_MODULE::HEADPOSTURE"))

(in-package "ROS")
;;//! \htmlinclude HeadPosture.msg.html


(defclass head_posture_module::HeadPosture
  :super ros::object
  :slots (_pose_visible _calibrated _head_down _posture_score _head_drop_ratio _baseline_ratio _consecutive_droop_frames _stamp ))

(defmethod head_posture_module::HeadPosture
  (:init
   (&key
    ((:pose_visible __pose_visible) nil)
    ((:calibrated __calibrated) nil)
    ((:head_down __head_down) nil)
    ((:posture_score __posture_score) 0.0)
    ((:head_drop_ratio __head_drop_ratio) 0.0)
    ((:baseline_ratio __baseline_ratio) 0.0)
    ((:consecutive_droop_frames __consecutive_droop_frames) 0)
    ((:stamp __stamp) (instance ros::time :init))
    )
   (send-super :init)
   (setq _pose_visible __pose_visible)
   (setq _calibrated __calibrated)
   (setq _head_down __head_down)
   (setq _posture_score (float __posture_score))
   (setq _head_drop_ratio (float __head_drop_ratio))
   (setq _baseline_ratio (float __baseline_ratio))
   (setq _consecutive_droop_frames (round __consecutive_droop_frames))
   (setq _stamp __stamp)
   self)
  (:pose_visible
   (&optional (__pose_visible :null))
   (if (not (eq __pose_visible :null)) (setq _pose_visible __pose_visible)) _pose_visible)
  (:calibrated
   (&optional (__calibrated :null))
   (if (not (eq __calibrated :null)) (setq _calibrated __calibrated)) _calibrated)
  (:head_down
   (&optional (__head_down :null))
   (if (not (eq __head_down :null)) (setq _head_down __head_down)) _head_down)
  (:posture_score
   (&optional __posture_score)
   (if __posture_score (setq _posture_score __posture_score)) _posture_score)
  (:head_drop_ratio
   (&optional __head_drop_ratio)
   (if __head_drop_ratio (setq _head_drop_ratio __head_drop_ratio)) _head_drop_ratio)
  (:baseline_ratio
   (&optional __baseline_ratio)
   (if __baseline_ratio (setq _baseline_ratio __baseline_ratio)) _baseline_ratio)
  (:consecutive_droop_frames
   (&optional __consecutive_droop_frames)
   (if __consecutive_droop_frames (setq _consecutive_droop_frames __consecutive_droop_frames)) _consecutive_droop_frames)
  (:stamp
   (&optional __stamp)
   (if __stamp (setq _stamp __stamp)) _stamp)
  (:serialization-length
   ()
   (+
    ;; bool _pose_visible
    1
    ;; bool _calibrated
    1
    ;; bool _head_down
    1
    ;; float32 _posture_score
    4
    ;; float32 _head_drop_ratio
    4
    ;; float32 _baseline_ratio
    4
    ;; int32 _consecutive_droop_frames
    4
    ;; time _stamp
    8
    ))
  (:serialize
   (&optional strm)
   (let ((s (if strm strm
              (make-string-output-stream (send self :serialization-length)))))
     ;; bool _pose_visible
       (if _pose_visible (write-byte -1 s) (write-byte 0 s))
     ;; bool _calibrated
       (if _calibrated (write-byte -1 s) (write-byte 0 s))
     ;; bool _head_down
       (if _head_down (write-byte -1 s) (write-byte 0 s))
     ;; float32 _posture_score
       (sys::poke _posture_score (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;; float32 _head_drop_ratio
       (sys::poke _head_drop_ratio (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;; float32 _baseline_ratio
       (sys::poke _baseline_ratio (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;; int32 _consecutive_droop_frames
       (write-long _consecutive_droop_frames s)
     ;; time _stamp
       (write-long (send _stamp :sec) s) (write-long (send _stamp :nsec) s)
     ;;
     (if (null strm) (get-output-stream-string s))))
  (:deserialize
   (buf &optional (ptr- 0))
   ;; bool _pose_visible
     (setq _pose_visible (not (= 0 (sys::peek buf ptr- :char)))) (incf ptr- 1)
   ;; bool _calibrated
     (setq _calibrated (not (= 0 (sys::peek buf ptr- :char)))) (incf ptr- 1)
   ;; bool _head_down
     (setq _head_down (not (= 0 (sys::peek buf ptr- :char)))) (incf ptr- 1)
   ;; float32 _posture_score
     (setq _posture_score (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;; float32 _head_drop_ratio
     (setq _head_drop_ratio (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;; float32 _baseline_ratio
     (setq _baseline_ratio (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;; int32 _consecutive_droop_frames
     (setq _consecutive_droop_frames (sys::peek buf ptr- :integer)) (incf ptr- 4)
   ;; time _stamp
     (send _stamp :sec (sys::peek buf ptr- :integer)) (incf ptr- 4)  (send _stamp :nsec (sys::peek buf ptr- :integer)) (incf ptr- 4)
   ;;
   self)
  )

(setf (get head_posture_module::HeadPosture :md5sum-) "cf8798f74ba00625c0c934cef96b9d09")
(setf (get head_posture_module::HeadPosture :datatype-) "head_posture_module/HeadPosture")
(setf (get head_posture_module::HeadPosture :definition-)
      "# Head posture evidence from the MediaPipe pose node.
# Input to the fatigue monitor; does not trigger speech by itself.

bool pose_visible
bool calibrated
bool head_down

float32 posture_score
float32 head_drop_ratio
float32 baseline_ratio

int32 consecutive_droop_frames
time stamp

")



(provide :head_posture_module/HeadPosture "cf8798f74ba00625c0c934cef96b9d09")


