
(cl:in-package :asdf)

(defsystem "vision_presence_module-msg"
  :depends-on (:roslisp-msg-protocol :roslisp-utils )
  :components ((:file "_package")
    (:file "UserState" :depends-on ("_package_UserState"))
    (:file "_package_UserState" :depends-on ("_package"))
  ))