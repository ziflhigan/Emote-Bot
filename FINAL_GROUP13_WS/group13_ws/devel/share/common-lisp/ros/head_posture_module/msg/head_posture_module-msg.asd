
(cl:in-package :asdf)

(defsystem "head_posture_module-msg"
  :depends-on (:roslisp-msg-protocol :roslisp-utils )
  :components ((:file "_package")
    (:file "HeadPosture" :depends-on ("_package_HeadPosture"))
    (:file "_package_HeadPosture" :depends-on ("_package"))
  ))