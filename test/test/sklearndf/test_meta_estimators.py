import logging

import pandas as pd
import pytest
from sklearn.impute import SimpleImputer

from sklearndf.classification import (
    ClassifierChainDF,
    LogisticRegressionCVDF,
    LogisticRegressionDF,
    RandomForestClassifierDF,
    StackingClassifierDF,
    VotingClassifierDF,
)
from sklearndf.pipeline import ClassifierPipelineDF, PipelineDF, RegressorPipelineDF
from sklearndf.regression import (
    ElasticNetDF,
    LinearRegressionDF,
    MultiOutputRegressorDF,
    RandomForestRegressorDF,
    RidgeCVDF,
    StackingRegressorDF,
)
from sklearndf.transformation import ColumnTransformerDF, StandardScalerDF

log = logging.getLogger(__name__)


def test_meta_estimators() -> None:
    VotingClassifierDF(estimators=[("rf", RandomForestClassifierDF())])

    with pytest.raises(
        TypeError,
        match=(
            "sklearndf meta-estimators only accept simple regressors and classifiers, "
            "but got: ClassifierPipelineDF"
        ),
    ):
        VotingClassifierDF(
            estimators=[
                ("rf", ClassifierPipelineDF(classifier=RandomForestClassifierDF()))
            ]
        )

    MultiOutputRegressorDF(estimator=RandomForestRegressorDF())

    with pytest.raises(
        TypeError,
        match=(
            "sklearndf meta-estimators only accept simple regressors and classifiers, "
            "but got: RegressorPipelineDF"
        ),
    ):
        MultiOutputRegressorDF(
            estimator=RegressorPipelineDF(regressor=RandomForestRegressorDF())
        )

    ClassifierChainDF(base_estimator=RandomForestClassifierDF())

    with pytest.raises(
        TypeError,
        match=(
            "sklearndf meta-estimators only accept simple regressors and classifiers, "
            "but got: SimpleImputer"
        ),
    ):
        ClassifierChainDF(base_estimator=SimpleImputer())


def test_stacking_regressor(
    boston_features: pd.DataFrame, boston_target_sr: pd.Series
) -> None:

    # basic building blocks
    model1 = LinearRegressionDF()
    model2 = ElasticNetDF()
    feature_names = list(boston_features.columns)
    preprocessing = ColumnTransformerDF(
        [
            ("scaled", StandardScalerDF(), feature_names[1:]),
            ("keep", "passthrough", feature_names[:1]),
        ]
    )
    print(preprocessing)

    # Pipeline with stack works
    pipeline = PipelineDF(
        [
            ("preprocessing", preprocessing),
            (
                "stack",
                StackingRegressorDF(
                    [
                        ("model1", model1),
                        ("model2", model2),
                    ]
                ),
            ),
        ]
    )
    pipeline.fit(boston_features, boston_target_sr)
    print(pipeline.predict(boston_features))

    # Stack of Pipelines doesn't
    stack_of_pipelines = StackingRegressorDF(
        estimators=[
            (
                "pipeline1",
                PipelineDF([("preprocessing", preprocessing), ("model1", model1)]),
            ),
            (
                "pipeline2",
                PipelineDF([("preprocessing", preprocessing), ("model2", model2)]),
            ),
            ("ignore", "drop"),
        ],
        final_estimator=RidgeCVDF(),
    )
    stack_of_pipelines.fit(boston_features, boston_target_sr)

    pred = stack_of_pipelines.predict(boston_features)
    assert isinstance(pred, pd.Series)

    assert not stack_of_pipelines.final_estimator.is_fitted
    final_estimator_fitted = stack_of_pipelines.final_estimator_
    assert final_estimator_fitted.feature_names_in_.to_list() == [
        "pipeline1",
        "pipeline2",
    ]


def test_stacking_classifier(
    iris_features: pd.DataFrame, iris_target_sr: pd.Series
) -> None:

    # basic building blocks
    model1 = LogisticRegressionCVDF()
    model2 = RandomForestClassifierDF(max_depth=5)
    feature_names = iris_features.columns.to_list()
    preprocessing = ColumnTransformerDF(
        [
            ("scaled", StandardScalerDF(), feature_names[1:]),
            ("keep", "passthrough", feature_names[:1]),
        ]
    )

    # Pipeline with stack works
    pipeline = PipelineDF(
        [
            ("preprocessing", preprocessing),
            (
                "stack",
                StackingClassifierDF(
                    [
                        ("model1", model1),
                        ("model2", model2),
                    ]
                ),
            ),
        ]
    )
    pipeline.fit(iris_features, iris_target_sr)
    print(pipeline.predict(iris_features))

    # Stack of Pipelines doesn't
    stack_of_pipelines = StackingClassifierDF(
        estimators=[
            (
                "pipeline1",
                PipelineDF([("preprocessing", preprocessing), ("model1", model1)]),
            ),
            (
                "pipeline2",
                PipelineDF([("preprocessing", preprocessing), ("model2", model2)]),
            ),
            ("ignore", "drop"),
        ],
        final_estimator=LogisticRegressionDF(),
        passthrough=True,
    )
    stack_of_pipelines.fit(iris_features, iris_target_sr)

    pred = stack_of_pipelines.predict_proba(iris_features)
    assert pred.columns.to_list() == ["setosa", "versicolor", "virginica"]

    assert not stack_of_pipelines.final_estimator.is_fitted
    final_estimator_fitted = stack_of_pipelines.final_estimator_
    assert final_estimator_fitted.feature_names_in_.to_list() == [
        "pipeline1_setosa",
        "pipeline1_versicolor",
        "pipeline1_virginica",
        "pipeline2_setosa",
        "pipeline2_versicolor",
        "pipeline2_virginica",
        "sepal length (cm)",
        "sepal width (cm)",
        "petal length (cm)",
        "petal width (cm)",
    ]
