      export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-17.0.10.0.7-2.el9.x86_64
     export PATH=$JAVA_HOME:$JAVA_HOME/bin:$PATH
     echo $JAVA_HOME
ls /opt/maven
     #sudo ln -s /opt/maven/apache-maven-3.8.4 /opt/maven/latest
     export M2_HOME=/opt/maven/latest
     export MAVEN_HOME=/opt/maven/latest
      export PATH=${M2_HOME}/bin:${PATH}
     mvn -version

